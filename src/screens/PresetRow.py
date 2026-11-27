from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.Game import (
    PRESET_SKIP_KEY,
    PRESET_STAGE_KEY,
    PRESET_TYPE_KEY,
)
from automaton_gui.screens.AccountsFile import (
    ACCOUNT_PREFIX,
    DisplayAccountName,
    ExistingAccounts,
)
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.PresetStage import (
    PresetStagePicker,
    ReadPresetStage,
    ShowStageOnButton,
    StageName,
)

# Shortcuts for what the preset launch modes (4/7) would otherwise make you
# open Account settings to change: which account and its auto-farm stage, on
# their own row. Every combo/button here is a FIXED width regardless of
# its content, since that's what stopped a long account/stage name from
# pushing the whole window wider. At winWidth=700 the account combo is the
# one that gives up width - the preset button keeps its room.
PRESET_ROW_SPACING = gc.SPACING_ROW
PRESET_LABEL_FONT_SIZE = gc.APP_FONT_POINT_SIZE
PRESET_COMBO_FONT_SIZE = gc.APP_FONT_POINT_SIZE
PRESET_COMBO_WIDTH = 100
PRESET_COMBO_MIN_HEIGHT = 34
COMBO_POPUP_MIN_WIDTH = 260
PRESET_BUTTON_MAX_WIDTH = 280


def Vsep() -> QLabel:
    """A greyed-out "|" marking the boundary between two shortcut groups on
    the same row - cheaper than a QFrame vline and matches how "subtle" text
    already reads elsewhere (the subtitle, the coffee-claimed label)."""
    sep = QLabel("|")
    sep.setProperty("subtle", True)
    return sep


def NarrowCombo(combo: QComboBox, width: int) -> None:
    """Fix the CLOSED box at `width` regardless of item text - a QComboBox's
    natural sizeHint grows to fit its longest item, which is exactly what let
    one long team/stage name push the whole window wider. The dropdown POPUP
    is given its own, wider minimum instead, so opening it still shows full
    item text; only the closed state is compact."""
    combo.setFixedWidth(width)
    combo.setMinimumHeight(PRESET_COMBO_MIN_HEIGHT)
    combo.view().setMinimumWidth(max(width, COMBO_POPUP_MIN_WIDTH))


class PresetRowMixin:
    """The account / preset stage / skip toggle row shared by the launch and
    macro windows. None of it goes over the bridge: it writes Accounts.ini / the
    conf directly with IniApply, the same way _PersistTheme does for the config
    menu bar, and the picker opens in-process like the other editors
    (BuildConfigMenus._open's pattern). Needs `self._config` on the host."""

    _accountCombo: QComboBox | None = None
    _presetButton: QPushButton | None = None
    _skipCheck: QCheckBox | None = None
    _presetPicker: QWidget | None = None

    def _PresetRow(self) -> QHBoxLayout | None:
        cfg = self._config
        if cfg is None or not cfg.accountsFile:
            return None
        hasStagePicker = bool(PRESET_TYPE_KEY and PRESET_STAGE_KEY)

        row = QHBoxLayout()
        row.setSpacing(PRESET_ROW_SPACING)

        accountLabel = QLabel(self.T("launch.account", "Account"))
        ApplyFont(accountLabel, PRESET_LABEL_FONT_SIZE)
        row.addWidget(accountLabel)

        sections = ExistingAccounts(cfg.accountsFile) or [f"{ACCOUNT_PREFIX}0"]
        accountCombo = QComboBox()
        for section in sections:
            accountCombo.addItem(DisplayAccountName(cfg.accountsFile, section), section)
        active = IniRead(cfg.confFile, "General", "activeAccount", "0")
        wanted = f"{ACCOUNT_PREFIX}{active}"
        index = next((i for i in range(accountCombo.count())
                      if accountCombo.itemData(i) == wanted), None)
        if index is None:
            # active account doesn't exist: adopt the one shown, or AHK and this row disagree
            index = 0
            IniApply(cfg.confFile, {("General", "activeAccount"): sections[0][len(ACCOUNT_PREFIX):]})
        accountCombo.setCurrentIndex(index)
        NarrowCombo(accountCombo, PRESET_COMBO_WIDTH)
        ApplyFont(accountCombo, PRESET_COMBO_FONT_SIZE)
        accountCombo.currentIndexChanged.connect(self._AccountChanged)
        self._accountCombo = accountCombo
        row.addWidget(accountCombo)

        if hasStagePicker:
            row.addWidget(Vsep())

            presetLabel = QLabel(self.T("launch.preset_stage_label", "Preset stage"))
            ApplyFont(presetLabel, PRESET_LABEL_FONT_SIZE)
            row.addWidget(presetLabel)

            self._presetButton = QPushButton()
            self._presetButton.setMaximumWidth(PRESET_BUTTON_MAX_WIDTH)
            self._presetButton.clicked.connect(self._OpenPresetPicker)
            row.addWidget(self._presetButton, 1)

            self._skipCheck = QCheckBox(self.T("launch.skip_picker", "Skip picker"))
            self._skipCheck.toggled.connect(self._SkipToggled)
            row.addWidget(self._skipCheck)
        else:
            row.addStretch(1)

        self._RefreshPresetRow()
        return row

    def _CurrentAccountSection(self) -> str | None:
        return self._accountCombo.currentData() if self._accountCombo is not None else None

    def _SyncAccountCombo(self) -> None:
        """Re-select the account combo from conf's activeAccount - called after
        General settings changes it there, so this row doesn't keep showing a
        stale selection until the window is reopened."""
        if self._accountCombo is None:
            return
        active = IniRead(self._config.confFile, "General", "activeAccount", "0")
        wanted = f"{ACCOUNT_PREFIX}{active}"
        index = next((i for i in range(self._accountCombo.count())
                      if self._accountCombo.itemData(i) == wanted), -1)
        if index >= 0 and index != self._accountCombo.currentIndex():
            self._accountCombo.blockSignals(True)
            self._accountCombo.setCurrentIndex(index)
            self._accountCombo.blockSignals(False)
        self._RefreshPresetRow()

    def _RefreshPresetRow(self) -> None:
        section = self._CurrentAccountSection()
        if section is None:
            return
        accountsFile = self._config.accountsFile
        # the combo's item text is a snapshot from build time - a rename in
        # Account settings must not need a reopen to show up here
        for i in range(self._accountCombo.count()):
            itemSection = self._accountCombo.itemData(i)
            self._accountCombo.setItemText(i, DisplayAccountName(accountsFile, itemSection))
        if self._presetButton is None:
            return
        typeID, stageID = ReadPresetStage(accountsFile, section)
        notSet = self.T("launch.preset_not_set", "not set")
        # "Preset stage" is its own label now (matches Account/Team preset),
        # so the button carries only the stage name.
        ShowStageOnButton(
            self._presetButton,
            StageName(self._config.stageStages, typeID, stageID, notSet),
            PRESET_BUTTON_MAX_WIDTH,
        )
        skip = IniRead(accountsFile, section, PRESET_SKIP_KEY, "0").strip() == "1"
        self._skipCheck.blockSignals(True)
        self._skipCheck.setChecked(skip)
        self._skipCheck.blockSignals(False)

    def _AccountChanged(self, index: int) -> None:
        section = self._accountCombo.itemData(index) if index >= 0 else None
        if section is None:
            return
        IniApply(self._config.confFile, {("General", "activeAccount"): section[len(ACCOUNT_PREFIX):]})
        self._RefreshPresetRow()

    def _SkipToggled(self, checked: bool) -> None:
        section = self._CurrentAccountSection()
        if section is None:
            return
        IniApply(self._config.accountsFile, {(section, PRESET_SKIP_KEY): 1 if checked else 0})

    # The "Preset stage" button: same picker, but nothing is launching - it
    # only SAVES a stage for the preset launch modes to use later. pickOnly
    # swaps "Start Combat" for "Select stage" and hides "Spends all available
    # battery" (both would be false claims here); a confirm just re-syncs the
    # row and a cancel does nothing at all.
    def _OpenPresetPicker(self) -> None:
        section = self._CurrentAccountSection()
        if section is None:
            return
        self._presetPicker = self._BuildPresetPicker(
            section, lambda *_a: self._RefreshPresetRow(), pickOnly=True)
        self._presetPicker.ShowCentered()

    def _BuildPresetPicker(
        self, section: str, onPicked: Callable[[int, int], None], pickOnly: bool = False,
    ):
        cfg = self._config
        # the launch window's team dropdown is the launcher's team, even before it is saved
        teamCombo = getattr(self, "_teamCombo", None)
        return PresetStagePicker(
            cfg.accountsFile,
            section,
            cfg.stageTypes,
            cfg.stageStages,
            cfg.placeholder,
            onPicked,
            pickOnly,
            self,
            stageTeams=cfg.stageTeams,
            defaultTeam=teamCombo.currentData() if teamCombo is not None else None,
        )

    # Belt-and-suspenders: the Account settings save already refreshes this
    # row directly (config_menu.py's _AccountSettingsSaved), but re-syncing
    # on every reactivation too - a child editor closing, alt-tab back - means
    # a stale caption can't survive being looked at, regardless of which path
    # touched Accounts.ini.
    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._RefreshPresetRow()
