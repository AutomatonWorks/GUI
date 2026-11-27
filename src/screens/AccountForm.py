from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QWidget

from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.screens.PresetStage import (
    PresetStagePicker,
    ReadPresetStage,
    ShowStageOnButton,
    StageName,
)
from automaton_gui.screens.SettingsSchema import Setting, SettingType
from automaton_gui.Game import PRESET_SKIP_KEY
from automaton_gui.theme.Palettes import HexOf
from automaton_gui.theme.Theme import theme

# ---- layout constants (edit these to restyle the account form) ----
FORM_MARGINS = (20, 16, 20, 16)
FORM_ROW_SPACING = 6
# group titles: small, subtle, underlined, a little air above all but the first
GROUP_TITLE_FONT_SIZE = 10
GROUP_TITLE_TOP_GAP = 8
GROUP_TITLE_UNDERLINE_GAP = 3
LABEL_FIELD_GAP = 10
PAIR_GAP = 26
# field widths by type; a Setting's own `width` wins
TEXT_FIELD_WIDTH = 150
NUMBER_FIELD_WIDTH = 64
PASSWORD_FIELD_WIDTH = 210

# columns: label, field, gap, label, field, then the slack
FIRST_LABEL_COLUMN = 0
FIRST_FIELD_COLUMN = 1
PAIR_GAP_COLUMN = 2
SECOND_LABEL_COLUMN = 3
SECOND_FIELD_COLUMN = 4
SLACK_COLUMN = 5
FORM_COLUMNS = 6

LEFT_ALIGNED = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def GroupTitle(text: str, topGap: bool) -> QLabel:
    label = QLabel(text)
    ApplyFont(label, GROUP_TITLE_FONT_SIZE, bold=True)
    label.setProperty("subtle", True)
    label.setStyleSheet(
        f"border-bottom: 1px solid {HexOf(theme.palette.sep)}; padding-bottom: {GROUP_TITLE_UNDERLINE_GAP}px;")
    if topGap:
        label.setContentsMargins(0, GROUP_TITLE_TOP_GAP, 0, 0)
    return label


def FieldWidth(s: Setting) -> int:
    """The fixed width of a setting's field in the account form; 0 leaves it at its natural size."""
    if s.width:
        return s.width
    if s.type == SettingType.BOOL:
        return 0
    if s.type == SettingType.NUMBER:
        return NUMBER_FIELD_WIDTH
    if s.type == SettingType.PASSWORD:
        return PASSWORD_FIELD_WIDTH
    return TEXT_FIELD_WIDTH


class AccountForm:
    """The selected account's settings form in AccountManagerGUI, plus its preset-stage button.
    Needs the window's `file`, `settings`, `_settingDefs`, `_presetButtons`, `_childEditors`,
    the stage tables and the field engine (SettingFields).

    One grid for the whole form (label, field, gap, label, field): every label has its own
    column, so the inputs and selects of each column start at the same x down the window."""

    def _AccountForm(self, section: str) -> QWidget:
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(*FORM_MARGINS)
        grid.setHorizontalSpacing(LABEL_FIELD_GAP)
        grid.setVerticalSpacing(FORM_ROW_SPACING)
        grid.setColumnMinimumWidth(PAIR_GAP_COLUMN, PAIR_GAP - (2 * LABEL_FIELD_GAP))
        grid.setColumnStretch(SLACK_COLUMN, 1)
        row = 0
        for index, group in enumerate(self._settingDefs):
            if group.title:
                grid.addWidget(GroupTitle(group.title, topGap=(index > 0)), row, 0, 1, FORM_COLUMNS)
                row += 1
            for rowSettings in group.rows:
                self._AddSettingsRow(grid, row, section, rowSettings)
                row += 1
        grid.setRowStretch(row, 1)
        return content

    # The preset-stage row leads with a button opening StageSelectGUI rather than a
    # Setting-driven widget, spotted by PRESET_SKIP_KEY being in the row (see
    # account_schema's docstring for why the picker replaced the old dropdown pair).
    def _AddSettingsRow(self, grid: QGridLayout, row: int, section: str, rowSettings: list[Setting]) -> None:
        pairs = [self._AccountPair(section, shared) for shared in rowSettings]
        if any((s.key == PRESET_SKIP_KEY) for s in rowSettings):
            stageLabel = QLabel(self.T("account_settings.preset_stage.label", "Stage"))
            pairs.insert(0, (stageLabel, self._BuildPresetStageButton(section)))
        columns = [(FIRST_LABEL_COLUMN, FIRST_FIELD_COLUMN), (SECOND_LABEL_COLUMN, SECOND_FIELD_COLUMN)]
        for (label, widget), (labelColumn, fieldColumn) in zip(pairs, columns):
            grid.addWidget(label, row, labelColumn, LEFT_ALIGNED)
            grid.addWidget(widget, row, fieldColumn, LEFT_ALIGNED)

    def _AccountPair(self, section: str, shared: Setting) -> tuple[QLabel, QWidget]:
        # a copy, so SetChoices on this account leaves the schema the next one loads alone
        s = replace(shared)
        name = f"{section}.{s.key}"
        self.settings[name] = s
        label, widget = self._LabelledField(name, s)
        width = FieldWidth(s)
        if width:
            widget.setFixedWidth(width)
        self._RegisterRow(name, label, widget)
        # a row that comes and goes keeps its room, so the columns never shift
        if s.shownWhen or s.shownBy:
            for part in (label, widget):
                policy = part.sizePolicy()
                policy.setRetainSizeWhenHidden(True)
                part.setSizePolicy(policy)
        return label, widget

    # ---- preset-stage picker button (reuses StageSelectGUI outright) -------
    def _BuildPresetStageButton(self, section: str) -> QPushButton:
        button = QPushButton()
        button.setFixedWidth(TEXT_FIELD_WIDTH)
        button.clicked.connect(lambda _=False, sec=section: self._OpenPresetStagePicker(sec))
        self._presetButtons[section] = button
        self._RefreshPresetStageButton(section)
        return button

    def _RefreshPresetStageButton(self, section: str) -> None:
        button = self._presetButtons.get(section)
        if button is None:
            return
        typeID, stageID = ReadPresetStage(self.file, section)
        notSet = self.T("account_settings.preset_stage_not_set", "not set")
        ShowStageOnButton(button, StageName(self._stageStages, typeID, stageID, notSet), TEXT_FIELD_WIDTH)

    # A confirmed stage is written the moment it is picked - same as the launch
    # window's own "Preset stage" button - rather than waiting for the Save button,
    # since it is the same picker being reused, not a plain field edit.
    def _OpenPresetStagePicker(self, section: str) -> None:
        picker = PresetStagePicker(
            self.file,
            section,
            self._stageTypes,
            self._stageStages,
            self._placeholder,
            onPicked=lambda *_picked: self._RefreshPresetStageButton(section),
            pickOnly=True,
            parent=self,
            stageTeams=self._stageTeams,
        )
        self._childEditors.append(picker)
        picker.ShowCentered()
