from __future__ import annotations

from automaton_gui import Game as game_conf
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator, QPixmap
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.SvgArt import IsSvg, ThemedSvgPixmap
from automaton_gui.framework.Widgets import ApplyFont, StackSprites, TrimTransparent
from automaton_gui.screens.TeamPicker import TeamPicker, CaptionLabel
from automaton_gui.screens.StageModel import (
    AMOUNT_RANGE_ENERGY,
    BONUS_CHOOSE,
    BONUS_CLAIMED,
    BONUS_HIDDEN,
    BONUS_OFF,
    ENERGY,
    FACT_RUNS,
    FACT_SPENT,
    FACT_UNITS,
    StageType,
)
from automaton_gui.screens.StagePreview import OptimalRuns, RunsSummary, SpentAndRuns
from automaton_gui.screens.WrappingValue import WrappingValue

# ---- layout constants (edit these to restyle the amount column) ----
AMOUNT_COLUMN_SPACING = 6
# The stage art is two icons side by side: stacked next to the amount fields while
# there are any, side by side over the team in the preset pickers.
ICON_STACKED_SIZE = (96, 200)
ICON_WIDE_SIZE = (240, 96)
ICON_GAP = 24
BONUS_TOP_GAP = 10
PRESET_BLOCK_GAP = 30
TEAM_PORTRAIT_PX = 60
TEAM_PORTRAIT_PX_PRESET = 80
AMOUNT_FIELD_FONT_SIZE = 24
AMOUNT_FIELD_MIN_HEIGHT = 46
AMOUNT_MAX_LEN_ENERGY = 4
STEPPER_FONT_SIZE = 18
BONUS_ROW_MARGINS = (6, 0, 6, 0)
FACT_SPACING = 2
FACT_NAME_GAP = 12
# bonus text and the spent / units / runs lines all read as one
# block of supporting detail, so they share one size
INFO_FONT_SIZE = 12
PRESET_NOTE_FONT_SIZE = 14
OPTIMIZE_BUTTON_MIN_HEIGHT = 40
OPTIMIZE_BUTTON_FONT_SIZE = 13
ROW_SPACING = gc.SPACING_ROW


class StageAmountPanel:
    """StageSelectGUI's right column: the stage icon, the amount field with its stepper, the
    bonus toggle, the live breakdown of what the amount turns into, the team and Optimize
    runs. Needs the window's `_preset`, `_pickOnly`, `_energy`, `_bonus`, `_maxUnits`,
    `_placeholder`, `_teamChoice`, `t`, `_CurrentType` and `_CurrentStage`."""

    # Three groups spread over the column's height: amount fields with the art beside
    # them, the team, and Optimize at the bottom.
    def _AmountColumn(self) -> QVBoxLayout:
        if self._preset:
            return self._PresetColumn()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(self._PresetNoteLabel())
        top = QHBoxLayout()
        top.setSpacing(ICON_GAP)
        top.addLayout(self._AmountFields(), 1)
        top.addWidget(self._IconSlot(ICON_STACKED_SIZE), 0, Qt.AlignmentFlag.AlignVCenter)
        col.addLayout(top)
        col.addStretch(1)
        team = self._TeamBlock(TEAM_PORTRAIT_PX)
        if team is not None:
            col.addWidget(team)
            col.addStretch(1)
        # Bottom of the column, styled like Start Combat: both are actions, and
        # this one belongs with the numbers it rewrites rather than beside it.
        col.addWidget(self._OptimizeButton())
        return col

    # No amount to type: the art and the team, centred. The amount widgets are still
    # built (half this class reads them unconditionally) and stay hidden.
    def _PresetColumn(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(PRESET_BLOCK_GAP)
        col.addStretch(1)
        col.addWidget(self._PresetNoteLabel())
        col.addWidget(self._IconSlot(ICON_WIDE_SIZE), 0, Qt.AlignmentFlag.AlignHCenter)
        team = self._TeamBlock(TEAM_PORTRAIT_PX_PRESET)
        if team is not None:
            col.addWidget(team)
        col.addLayout(self._AmountFields())
        col.addWidget(self._OptimizeButton())
        col.addStretch(1)
        self._HideAmountInputs()
        return col

    def _AmountFields(self) -> QVBoxLayout:
        fields = QVBoxLayout()
        fields.setSpacing(AMOUNT_COLUMN_SPACING)
        self._amountTitle = CaptionLabel(self.T("stage_select.energy", "Energy"))
        fields.addWidget(self._amountTitle)
        self._amount = self._AmountField()
        fields.addLayout(self._AmountRow())
        fields.addSpacing(BONUS_TOP_GAP)
        fields.addLayout(self._BonusRow())
        fields.addWidget(self._BreakdownBlock())
        self._unavailableNote = self._NoteLabel("")
        self._unavailableNote.setVisible(False)
        fields.addWidget(self._unavailableNote)
        fields.addStretch(1)
        return fields

    def _TeamBlock(self, portraitPx: int) -> TeamPicker | None:
        if self._teamChoice is None:
            return None
        self._teamPicker = TeamPicker(
            self._teamChoice.teams, self.T("stage_select.team", "Team"), portraitPx, self._teamChoice.placeholder)
        self._teamPicker.SetTeam(self._teamChoice.TeamFor(0, 0))
        return self._teamPicker

    def _IconSlot(self, size: tuple[int, int]) -> QLabel:
        self._icon = QLabel()
        self._iconSize = size
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setFixedSize(*size)
        self._icon.setProperty("subtle", True)
        return self._icon

    def _NoteLabel(self, text: str) -> QLabel:
        note = QLabel(text)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setProperty("subtle", True)
        note.setWordWrap(True)
        ApplyFont(note, PRESET_NOTE_FONT_SIZE)
        return note

    def _PresetNoteLabel(self) -> QLabel:
        self._presetNote = self._NoteLabel(self.T("stage_select.preset_note", "Spends all available energy."))
        self._presetNote.setVisible(self._preset and not self._pickOnly)
        return self._presetNote

    def _AmountField(self) -> QLineEdit:
        amount = QLineEdit()
        amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        amount.setMaxLength(AMOUNT_MAX_LEN_ENERGY)
        amount.setValidator(QIntValidator(*AMOUNT_RANGE_ENERGY, amount))
        ApplyFont(amount, AMOUNT_FIELD_FONT_SIZE)
        amount.setMinimumHeight(AMOUNT_FIELD_MIN_HEIGHT)
        amount.returnPressed.connect(self.OnEnter)
        amount.textChanged.connect(lambda _t: self._RefreshInputs())
        return amount

    # What the picked amount/bonus/units actually turn into, so the run
    # count is visible BEFORE committing rather than in the confirm box.
    # One fact per row, name left and value right, so neither ever shares a
    # line with the other or wraps into it.
    def _BreakdownBlock(self) -> QWidget:
        self._breakdown = QWidget()
        facts = QVBoxLayout(self._breakdown)
        facts.setContentsMargins(*BONUS_ROW_MARGINS)
        facts.setSpacing(FACT_SPACING)
        factNames = {
            FACT_SPENT: self.T("stage_select.energy_spent", "Energy spent"),
            FACT_UNITS: self.T("stage_select.units", "Units"),
            FACT_RUNS: self.T("stage_select.runs", "Runs"),
        }
        for fact in self._energy.facts:
            self._factValues[fact] = self._FactRow(facts, factNames[fact])
        return self._breakdown

    def _OptimizeButton(self) -> QPushButton:
        self._optimize = QPushButton(self.T("stage_select.optimize_runs", "Optimize runs"))
        self._optimize.setProperty("primary", True)
        self._optimize.setMinimumHeight(OPTIMIZE_BUTTON_MIN_HEIGHT)
        self._optimize.setCursor(Qt.CursorShape.PointingHandCursor)
        ApplyFont(self._optimize, OPTIMIZE_BUTTON_FONT_SIZE, bold=True)
        self._optimize.clicked.connect(self._OptimizeRuns)
        # a type without Optimize keeps its slot empty, so the team above never moves
        policy = self._optimize.sizePolicy()
        policy.setRetainSizeWhenHidden(game_conf.OPTIMIZE_RUNS and not self._preset)
        self._optimize.setSizePolicy(policy)
        self._optimize.setVisible(game_conf.OPTIMIZE_RUNS)
        return self._optimize

    # Preset launch: the run spends whatever the account has, so there is no
    # amount to type, no bonus to weigh and nothing to optimise. The widgets
    # stay built (half this class reads them unconditionally) and just hide.
    def _HideAmountInputs(self) -> None:
        for widget in (self._amountTitle, self._amount, self._stepper, self._breakdown,
                       self._optimize, self._bonusCheck, self._bonusText,
                       self._bonusLabel):
            if widget is not None:
                widget.setVisible(False)

    # The amount field, with the +/- stepper on its right when the game asks for one:
    # + over -, each half the field's height and twice as wide as it is tall.
    def _AmountRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(AMOUNT_COLUMN_SPACING)
        row.addWidget(self._amount, 1)

        self._stepper = QWidget()
        buttons = QVBoxLayout(self._stepper)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(0)
        buttonHeight = AMOUNT_FIELD_MIN_HEIGHT // 2
        for text, direction in (("+", 1), ("-", -1)):
            button = QPushButton(text)
            button.setFixedSize(2 * buttonHeight, buttonHeight)
            button.setAutoRepeat(True)
            ApplyFont(button, STEPPER_FONT_SIZE, bold=True)
            button.clicked.connect(lambda _c=False, d=direction: self._StepAmount(d))
            buttons.addWidget(button)
        row.addWidget(self._stepper)
        if self._energy.stepper:
            self._amount.setFixedHeight(2 * buttonHeight)
        self._stepper.setVisible(False)
        return row

    # + goes to the next multiple of the step above the value, - to the next one
    # below, both kept inside the type's range.
    def _StepAmount(self, direction: int) -> None:
        stageType = self._CurrentType()
        if stageType is None or not stageType.step:
            return
        step = stageType.step
        value = self._AmountValue()
        if direction > 0:
            value = (value // step + 1) * step
        else:
            value = ((value - 1) // step) * step
        value = max(stageType.minAmount, min(stageType.maxAmount, value))
        self._amount.setText(str(value))

    def _AmountValue(self) -> int:
        return int(self._amount.text()) if self._amount.text() else 0

    # The bonus slot under the amount field: an interactive on/off checkbox while the bonus is up for grabs, a "claimed" notice once it is gone, or nothing when the game has none.
    # The box sits at the column's left edge and its text is a separate right-aligned label (a bare checkbox glues text to the box); the label forwards clicks so the whole row still toggles.
    # The text carries the live preview; only the box's checked state rides back to AHK.
    def _BonusRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(*BONUS_ROW_MARGINS)
        row.setSpacing(ROW_SPACING)
        if self._bonus.state == BONUS_CHOOSE:
            self._bonusCheck = QCheckBox()
            self._bonusCheck.setChecked(self._bonus.checked)
            self._bonusCheck.toggled.connect(lambda _c: self._RefreshInputs())
            self._bonusText = QLabel()
            self._bonusText.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._bonusText.mousePressEvent = self._ToggleBonusFromText
            ApplyFont(self._bonusText, INFO_FONT_SIZE)
            row.addWidget(self._bonusCheck)
            row.addWidget(self._bonusText)
            row.addStretch(1)
        elif self._bonus.state == BONUS_CLAIMED:
            self._bonusLabel = QLabel(self.T("stage_select.bonus_claimed", "Bonus already claimed"))
            self._bonusLabel.setProperty("subtle", True)
            self._bonusLabel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            ApplyFont(self._bonusLabel, INFO_FONT_SIZE)
            row.addWidget(self._bonusLabel, 1)
        return row

    # Clicking the (separated) text label toggles the box, so the row behaves like
    # one checkbox; ignored while the box is disabled (a type locked to the off bonus).
    def _ToggleBonusFromText(self, event) -> None:
        if self._bonusCheck is not None and self._bonusCheck.isEnabled():
            self._bonusCheck.toggle()

    def _FactRow(self, parent: QVBoxLayout, name: str) -> WrappingValue:
        """One "name ....... value" line; returns the value to fill in. A long value wraps
        under itself rather than pushing the stage list aside."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(FACT_NAME_GAP)
        label = QLabel(name)
        label.setProperty("subtle", True)
        ApplyFont(label, INFO_FONT_SIZE)
        value = WrappingValue()
        value.label.setProperty("subtle", True)
        ApplyFont(value.label, INFO_FONT_SIZE)
        row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(value, 1)
        parent.addLayout(row)
        return value

    def _UnitsChoice(self) -> int:
        """Not user-editable: Optimize sets it, and it rides back on confirm so
        AHK stores it as the account setting it reads at dispatch."""
        return self._maxUnits

    def _MaxUnitsFor(self, stageType: StageType) -> int:
        if stageType.unitsAdjustable:
            return self._maxUnits
        stage = self._CurrentStage()
        if stage is not None and stage.maxUnits:
            return stage.maxUnits
        return stageType.maxUnits

    def _RefreshInputs(self) -> None:
        """Every input that can change the outcome funnels through here.

        _RefreshBonus returns early when the bonus slot is hidden or absent
        (a count type, or a bonus already claimed), so the breakdown cannot
        hang off its tail - it would simply never run for those."""
        if self._preset:
            return   # both would un-hide what _AmountColumn just hid
        self._RefreshBonus()
        self._RefreshBreakdown()

    def _RefreshBreakdown(self) -> None:
        stageType = self._CurrentType()
        blocked = stageType is not None and bool(stageType.unavailable)
        self._unavailableNote.setText(stageType.unavailable if blocked else "")
        self._unavailableNote.setVisible(blocked)
        applies = (stageType is not None and not blocked
                   and stageType.unit == ENERGY and stageType.step > 0)
        self._optimize.setVisible(game_conf.OPTIMIZE_RUNS and applies and stageType.unitsAdjustable)
        self._breakdown.setVisible(applies)
        if not applies:
            return
        spent, runs = SpentAndRuns(
            self._AmountValue(), stageType, self._energy, self._BonusChoice(), self._MaxUnitsFor(stageType))
        values = {
            FACT_SPENT: str(spent),
            FACT_UNITS: str(sum(runs) // stageType.step),
            FACT_RUNS: RunsSummary(runs),
        }
        for fact, label in self._factValues.items():
            label.setText(values[fact])

    def _OptimizeRuns(self) -> None:
        """Fill in the bonus and units per run needing the fewest runs; it does not confirm."""
        stageType = self._CurrentType()
        if stageType is None or stageType.unit != ENERGY or not stageType.step:
            return
        bonusOn, units = OptimalRuns(
            self._AmountValue(), stageType, self._energy, self._MaxUnitsFor(stageType))
        if self._bonusCheck is not None and stageType.bonusMode == BONUS_CHOOSE:
            self._bonusCheck.blockSignals(True)
            self._bonusCheck.setChecked(bonusOn)
            self._bonusCheck.blockSignals(False)
        if stageType.unitsAdjustable:
            self._maxUnits = units
        self._RefreshBonus()
        self._RefreshBreakdown()

    # ---- icon ----
    def _UpdateIcon(self) -> None:
        stage = self._CurrentStage()
        if stage is None or not stage.icon or not self._ShowIcon(stage.icon):
            self._ResetIcon()

    # Nothing picked yet (no stage, or the type just changed): show the logo
    # placeholder AHK resolved into the payload, not a bare "ZZZ" string. Falls
    # back to clearing the slot if the logo path is missing/unreadable.
    def _ResetIcon(self) -> None:
        if not (self._placeholder and self._ShowIcon(self._placeholder)):
            self._icon.setPixmap(QPixmap())
            self._icon.setText("")

    def _ShowIcon(self, path: str) -> bool:
        width, height = self._iconSize
        if IsSvg(path):
            art = ThemedSvgPixmap(path, width, height)
            if art is None:
                return False
            self._icon.setText("")
            self._icon.setPixmap(art)
            return True
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return False
        self._icon.setText("")
        art = StackSprites(pixmap) if height > width else TrimTransparent(pixmap)
        self._icon.setPixmap(
            art.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        return True

    # ---- bonus ----
    def _RefreshBonus(self) -> None:
        if self._bonusCheck is None:
            return
        stageType = self._CurrentType()
        if stageType is None:
            return
        hidden = stageType.bonusMode == BONUS_HIDDEN
        self._bonusCheck.setVisible(not hidden)
        self._bonusText.setVisible(not hidden)
        if hidden:
            return
        enabled = stageType.bonusMode != BONUS_OFF
        if not enabled and self._bonusCheck.isChecked():
            # A type locked to the off bonus is not togglable.
            self._bonusCheck.blockSignals(True)
            self._bonusCheck.setChecked(False)
            self._bonusCheck.blockSignals(False)
        self._bonusCheck.setEnabled(enabled)
        self._bonusText.setEnabled(enabled)
        bonusOn = self._bonusCheck.isChecked()
        bonus = self._bonus.on if bonusOn else self._bonus.off
        kind = (
            self.T("stage_select.bonus_on", "On")
            if bonusOn
            else self.T("stage_select.bonus_off", "Off")
        )
        self._bonusText.setText(
            self.T("stage_select.bonus_text", "{kind} (+{bonus})", kind=kind, bonus=bonus)
        )

    def _BonusChoice(self) -> bool:
        return bool(self._bonusCheck is not None and self._bonusCheck.isChecked())
