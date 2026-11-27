from __future__ import annotations

from typing import Callable

from automaton_gui.ipc import Reply
from automaton_gui import Game as game_conf
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.framework.Window import EnterRouter, GuiApp
from automaton_gui.I18n import T
from automaton_gui.screens.StageAmountPanel import AMOUNT_MAX_LEN_ENERGY, StageAmountPanel
from automaton_gui.screens.StageList import GroupedList
from automaton_gui.screens.StageModel import (
    AMOUNT_RANGE_ENERGY,
    COUNT,
    ENERGY,
    EnergyConfig,
    Stage,
    StageDefaults,
    StageType,
)
from automaton_gui.screens.StageTeam import TeamChoice, ActiveAccountSection, TeamChoiceFor
from automaton_gui.screens.WrappingValue import WrappingValue
from automaton_gui.screens.StageTypeChips import TypeChips
from automaton_gui.screens.TeamPicker import TeamPicker

# ---- layout constants (edit these to restyle this screen) ----
ROOT_MARGINS = (gc.MARGIN_SCREEN_SIDE, 14, gc.MARGIN_SCREEN_SIDE, 18)
ROOT_SPACING = gc.SPACING_SCREEN
COLUMNS_SPACING = 30
COLUMN_STRETCH = (47, 43)  # stage list / amount column
WIN_WIDTH = 960
WIN_HEIGHT = 618
# the preset pickers have no amount block, so they need less height
WIN_HEIGHT_PRESET = 528
STAGE_ROWS = 15
STAGE_ROWS_PRESET = 12
START_BUTTON_MIN_HEIGHT = 70
START_BUTTON_FONT_SIZE = 20

# StageSelectGUI ported from guis/StageSelectGUI.ahk2 + guis/StageSelectLogic.ahk2:
# the DB-driven stage-type / stage / amount picker the suites pop mid-run. The stage
# types are a row of chips on top; under it the stages of the picked type, and a right
# panel with the stage icon, the amount field whose label flips between the game's
# energy and "Runs", and the team (when the game sends teams) - over a primary Start
# button.
#
# Python stays dumb: the type/stage tables and the saved defaults arrive IN the
# show_stage_select payload (Python NEVER reads the AHK stage DB). The picked
# {typeId, stageId, amount} reports out through a callback so the IPC glue
# (OpenStageSelectGui) maps it onto the BLOCKING `stage_confirmed` /
# `stage_cancelled` catalog without the window knowing the channel exists. On the
# AHK side `show_stage_select` blocks (WaitForConfirm); here it is just a reply.
#
# The catalog response carries {typeId, stageId, amount, bonus, maxUnits}. AHK still
# owns the AUTHORITATIVE post-reply work: the rounding and the run breakdown
# (StageDatabaseCore RoundEnergy / SplitEnergy) and the OK/Cancel confirm MsgBox
# (same split as MacroMenu's confirm dialog staying AHK-side). The live preview runs
# the same rules from energy.py on the per-type numbers in the payload; the bonus
# toggle rides back so AHK applies the right one.
#
# The data classes are in stage_model.py, the type chips in stage_type_chips.py, the
# stage list in stageList.py, the amount column in stage_amount_panel.py, the team
# block in team_picker.py (its data in stage_team.py) and the preview math in
# stage_preview.py.


class StageSelectGUI(StageAmountPanel, GuiApp):
    winWidth = WIN_WIDTH
    winHeight = WIN_HEIGHT

    def __init__(
        self,
        types: list[StageType],
        stages: dict[int, list[Stage]],
        defaults: StageDefaults | None = None,
        onConfirm: Callable[[int, int, int, bool, int], None] | None = None,
        onCancel: Callable[[], None] | None = None,
        config=None,
        placeholder: str = "",
        energy: EnergyConfig | None = None,
        preset: bool = False,
        pickOnly: bool = False,
        teamChoice: TeamChoice | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._preset = bool(preset)
        if self._preset:
            self.winHeight = WIN_HEIGHT_PRESET
        self._teamPicker: TeamPicker | None = None
        # A preset-mode open that is ONLY saving a stage for later (the launch
        # window's "Preset stage" button) rather than about to run it right
        # now: "Start Combat" and "Spends all available energy" are both
        # wrong claims here, so both get swapped out. Implies preset=True's
        # amount/bonus/breakdown hiding either way - this only touches wording.
        self._pickOnly = bool(pickOnly)
        self._Load(types, stages, defaults, onConfirm, onCancel, config, placeholder, energy, teamChoice)
        self.layoutKey = StageLayoutKey(
            self._types, self._energy, self._preset, self._pickOnly, self._teamChoice, config)
        self._typeChips: TypeChips | None = None
        self._stageList: QListWidget | None = None
        self._amount: QLineEdit | None = None
        self._amountTitle: QLabel | None = None
        self._stepper: QWidget | None = None
        self._icon: QLabel | None = None
        self._presetNote: QLabel | None = None
        self._start: QPushButton | None = None
        self._bonusCheck = None
        self._bonusText: QLabel | None = None
        self._bonusLabel: QLabel | None = None
        self._breakdown: QWidget | None = None
        self._factValues: dict[str, WrappingValue] = {}
        self._unavailableNote: QLabel | None = None
        self._optimize: QPushButton | None = None
        self.title = T(
            config.strings if config else None,
            "stage_select.title",
            f"{game_conf.APP_NAME} | Stage Selection",
        )
        super().__init__(parent, strings=config.strings if config else None)

    # Everything a payload sets that the widgets only read, so reload can apply a new one.
    def _Load(self, types, stages, defaults, onConfirm, onCancel, config, placeholder, energy, teamChoice=None) -> None:
        if teamChoice is None:
            teamChoice = TeamChoiceFromConfig(config)
        self._teamChoice = teamChoice
        self._types = list(types)
        self._stages = {int(k): list(v) for k, v in stages.items()}
        self._defaults = defaults or StageDefaults()
        self._onConfirm = onConfirm
        self._onCancel = onCancel
        self._config = config
        self._placeholder = placeholder
        self._energy = energy or EnergyConfig()
        self._bonus = self._energy.bonus
        self._maxUnits = max(1, min(self._energy.unitsCap, self._energy.maxUnits))
        self._confirmed = False
        self._amounts: dict[int, str] = {}
        self._lastAmountByUnit: dict[str, str] = {}
        self._amountTypeId = 0

    # Building the window takes ~150 ms, so a closed one is shown again with the new payload when
    # it would build the same widgets (same layoutKey); the caller builds a new one otherwise.
    def Reload(self, types, stages, defaults, onConfirm, onCancel, config, placeholder, energy) -> None:
        self._Load(types, stages, defaults, onConfirm, onCancel, config, placeholder, energy)
        self.menuBar().clear()
        self._menus.clear()
        self._themeActions.clear()
        self.Menu()
        if self._bonusCheck is not None:
            self._bonusCheck.blockSignals(True)
            self._bonusCheck.setChecked(self._bonus.checked)
            self._bonusCheck.blockSignals(False)
        self._ApplyDefaults(True)

    # The shared config menu bar (Configuration/Locks/Theme/Help, ported from
    # ZzzGui.Menu) like the launch + macro windows; build it when the host
    # supplied the config data, else just the base Theme menu (the payload-less
    # preview/manual-poke path).
    def Menu(self) -> None:
        if self._config is not None:
            from automaton_gui.screens.ConfigMenu import BuildConfigMenus

            BuildConfigMenus(self, self._config)
        else:
            super().Menu()

    def Build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(*ROOT_MARGINS)
        root.setSpacing(ROOT_SPACING)

        self._typeChips = TypeChips()
        for stageType in self._types:
            self._typeChips.AddChip(stageType.name, stageType.id, stageType.badge)
        root.addWidget(self._typeChips)

        columns = QHBoxLayout()
        columns.setSpacing(COLUMNS_SPACING)
        self._stageList = GroupedList(STAGE_ROWS_PRESET if self._preset else STAGE_ROWS)
        stageColumn = QVBoxLayout()
        # the list grows up to its whole-row cap; what is left stays under it
        stageColumn.addWidget(self._stageList, 1)
        stageColumn.addStretch(0)
        columns.addLayout(stageColumn, COLUMN_STRETCH[0])
        columns.addLayout(self._AmountColumn(), COLUMN_STRETCH[1])
        root.addLayout(columns, 1)

        startLabel = (
            self.T("stage_select.pick_stage", "Select stage")
            if self._pickOnly
            else self.T("stage_select.start", "Start Combat")
        )
        self._start = QPushButton(startLabel)
        self._start.setProperty("primary", True)
        self._start.setMinimumHeight(START_BUTTON_MIN_HEIGHT)
        ApplyFont(self._start, START_BUTTON_FONT_SIZE, bold=True)
        self._start.clicked.connect(self._Confirm)

        root.addWidget(self._start)

        self.setCentralWidget(central)

        # Wire AFTER every widget exists: the dependent stage list reads the amount
        # label/field, which the type-change handler touches.
        self._typeChips.changed.connect(self._OnTypeChanged)
        self._stageList.itemSelectionChanged.connect(self._OnStageChanged)
        self.setTabOrder(self._typeChips, self._stageList)

    def OnBuilt(self) -> None:
        # the window is as wide as the chip row, so the chips end flush with Start
        self.resize(self._typeChips.SingleRowWidth() + ROOT_MARGINS[0] + ROOT_MARGINS[2], self.height())
        self._ApplyDefaults(False)

    # A reload may land on the type already picked, which emits no change, so it runs the change
    # itself to refill the stage list and the amount from the new payload.
    def _ApplyDefaults(self, forceTypeChange: bool) -> None:
        self._SelectTypeById(self._defaults.typeID)
        if forceTypeChange and self._CurrentTypeId():
            self._OnTypeChanged(self._CurrentTypeId())
        self._SelectStageById(self._defaults.stageID)
        if self._defaults.amount:
            self._amount.setText(str(self._defaults.amount))
        self._UpdateIcon()
        self._ApplyAvailability()
        self._RefreshInputs()
        self._RefreshStart()

    # ---- dependent dropdowns ----
    def _OnTypeChanged(self, typeID: int) -> None:
        stageType = self._TypeById(typeID)
        self._RememberAmount()
        self._PopulateStages(stageType.id)
        if stageType.unit == COUNT:
            self._amountTitle.setText(self.T("stage_select.runs", "Runs"))
            self._amount.setMaxLength(len(str(stageType.maxAmount)))
            self._amount.setValidator(
                QIntValidator(stageType.minAmount, stageType.maxAmount, self._amount))
        else:
            self._amountTitle.setText(self.T("stage_select.energy", "Energy"))
            self._amount.setMaxLength(AMOUNT_MAX_LEN_ENERGY)
            self._amount.setValidator(QIntValidator(*AMOUNT_RANGE_ENERGY, self._amount))
        self._amount.setText(self._AmountFor(stageType))
        self._amountTypeId = stageType.id
        self._stepper.setVisible(
            self._energy.stepper and not self._preset and stageType.unit == ENERGY and stageType.step > 0)
        self._ApplyAvailability()
        self._ResetIcon()
        self._ShowStageTeam()
        self._RefreshInputs()
        self._RefreshStart()

    # Leaving a type files its amount away, so a count type (whose field is a few
    # digits wide) cannot truncate the energy and coming back restores it.
    def _RememberAmount(self) -> None:
        previous = next((t for t in self._types if t.id == self._amountTypeId), None)
        if previous is None or previous.unavailable:
            return
        self._amounts[previous.id] = self._amount.text()
        self._lastAmountByUnit[previous.unit] = self._amount.text()

    def _AmountFor(self, stageType: StageType) -> str:
        if stageType.id in self._amounts:
            return self._amounts[stageType.id]
        if stageType.defaultAmount:
            return str(stageType.defaultAmount)
        if stageType.unit in self._lastAmountByUnit:
            return self._lastAmountByUnit[stageType.unit]
        return str(stageType.minAmount) if stageType.unit == COUNT else self._amount.text()

    # A type that cannot run right now (a weekly limit reached) zeroes the amount and
    # locks it; the breakdown shows why instead (_RefreshBreakdown).
    def _ApplyAvailability(self) -> None:
        stageType = self._CurrentType()
        blocked = stageType is not None and bool(stageType.unavailable)
        if blocked:
            self._amount.setText("0")
        self._amount.setEnabled(not blocked)
        self._stepper.setEnabled(not blocked)

    def _OnStageChanged(self) -> None:
        self._UpdateIcon()
        self._ShowStageTeam()
        self._RefreshInputs()
        self._RefreshStart()

    # Each stage shows the team it remembers, else the launcher's team; no stage, the logo.
    def _ShowStageTeam(self) -> None:
        if self._teamPicker is None:
            return
        if not self._CurrentStageId():
            self._teamPicker.ShowPlaceholder()
            return
        self._teamPicker.SetTeam(self._teamChoice.TeamFor(self._CurrentTypeId(), self._CurrentStageId()))

    def _PopulateStages(self, typeID: int) -> None:
        self._stageList.clear()
        group = ""
        for stage in self._stages.get(typeID, []):
            if stage.group and stage.group != group:
                self._stageList.AddGroupHeader(stage.group)
            group = stage.group
            self._stageList.AddRow(stage.label or stage.name, stage.id, stage.badge)

    # ---- selection helpers ----
    def _SelectTypeById(self, typeID: int) -> None:
        if not self._typeChips.SelectId(typeID):
            self._typeChips.SelectIndex(0)

    def _SelectStageById(self, stageID: int) -> None:
        for i in range(self._stageList.count()):
            if self._stageList.item(i).data(Qt.ItemDataRole.UserRole) == stageID:
                self._stageList.setCurrentRow(i)
                return

    def _TypeById(self, typeID: int) -> StageType:
        return next(t for t in self._types if t.id == typeID)

    def _CurrentType(self) -> StageType | None:
        typeID = self._CurrentTypeId()
        return self._TypeById(typeID) if typeID else None

    def _CurrentTypeId(self) -> int:
        return self._typeChips.CurrentId()

    def _CurrentStageId(self) -> int:
        selected = self._stageList.selectedItems()
        return selected[0].data(Qt.ItemDataRole.UserRole) if selected else 0

    def _CurrentStage(self) -> Stage | None:
        stageID = self._CurrentStageId()
        if not stageID:
            return None
        return next(
            (s for s in self._stages.get(self._CurrentTypeId(), []) if s.id == stageID),
            None,
        )

    # ---- start gating ----
    def _RefreshStart(self) -> None:
        # Start only once BOTH a type and a stage are actually picked (StageID 0 =
        # nothing chosen, as in UpdateGUI's `if stageID != 0`), and the type can run.
        self._start.setEnabled(
            bool(self._CurrentTypeId()) and bool(self._CurrentStageId()) and not self._Blocked())

    # Picking a preset stage only saves it for later, so an unavailable type
    # still blocks a run but not a pick.
    def _Blocked(self) -> bool:
        stageType = self._CurrentType()
        return not self._preset and stageType is not None and bool(stageType.unavailable)

    # ---- confirm / cancel ----
    # Enter goes straight to confirm once a type AND a stage are chosen; until then
    # it only parks focus on the first list still missing a pick (type, then
    # stage), never advancing past an unselected option. Mirrors AHK OnEnter.
    def OnEnter(self) -> None:
        if self._CurrentTypeId() and self._CurrentStageId():
            self._Confirm()
            return
        if not self._CurrentTypeId():
            self._typeChips.setFocus()
        else:
            self._stageList.setFocus()

    def _Confirm(self) -> None:
        if not self._CurrentTypeId() or not self._CurrentStageId() or self._Blocked():
            return
        self._confirmed = True
        if self._teamPicker is not None and self._teamChoice.onSave is not None:
            self._teamChoice.onSave(self._CurrentTypeId(), self._CurrentStageId(), self._teamPicker.TeamId())
        if self._preset:
            amount = 0
        else:
            amount = int(self._amount.text()) if self._amount.text() else 0
        if self._onConfirm is not None:
            self._onConfirm(
                self._CurrentTypeId(),
                self._CurrentStageId(),
                amount,
                self._BonusChoice(),
                self._UnitsChoice(),
            )
        self.close()

    # Dismissing without a pick (Escape, X) cancels. The AHK window set the global
    # closedGUi flag here; in the split architecture Python only reports it.
    def OnClose(self) -> bool:
        if not self._confirmed and self._onCancel is not None:
            self._onCancel()
        return False


def TeamChoiceFromConfig(config) -> TeamChoice | None:
    if (config is None) or (not getattr(config, "stageTeams", None)):
        return None
    return TeamChoiceFor(config.stageTeams, config.accountsFile, ActiveAccountSection(config.confFile))


def StageLayoutKey(types, energy, preset: bool, pickOnly: bool, teamChoice, config) -> tuple:
    """What the window's widgets are built from; two payloads with the same key build the same window."""
    energy = energy or EnergyConfig()
    chips = tuple((stageType.id, stageType.name, stageType.badge) for stageType in types)
    teams = None if (teamChoice is None) else (tuple(teamChoice.teams), teamChoice.placeholder)
    strings = tuple(sorted(config.strings.items())) if (config is not None) else None
    return (bool(preset), bool(pickOnly), chips, tuple(energy.facts), energy.stepper, energy.bonus.state, teams, strings)


def _ReplyCallbacks(reply: Reply):
    def OnConfirm(typeID: int, stageID: int, amount: int, bonusOn: bool,
                   maxUnits: int) -> None:
        reply("stage_confirmed", {
                "typeId": typeID,
                "stageId": stageID,
                "amount": amount,
                "bonus": 1 if bonusOn else 0,
                "maxUnits": maxUnits,
            },
        )

    def OnCancel() -> None:
        reply("stage_cancelled", {})

    return OnConfirm, OnCancel


def ReuseStageSelectGui(window: StageSelectGUI, reply: Reply, types, stages, defaults=None, config=None,
                           placeholder: str = "", energy: EnergyConfig | None = None) -> StageSelectGUI:
    """open_stage_select_gui on a closed window with the same layoutKey: reloads it and shows it again."""
    onConfirm, onCancel = _ReplyCallbacks(reply)
    window.Reload(types, stages, defaults, onConfirm, onCancel, config, placeholder, energy)
    EnterRouter.Instance().Register(window)
    window.ShowCentered()
    return window


def OpenStageSelectGui(
    reply: Reply,
    types: list[StageType],
    stages: dict[int, list[Stage]],
    defaults: StageDefaults | None = None,
    config=None,
    placeholder: str = "",
    energy: EnergyConfig | None = None,
    preset: bool = False,
    show: bool = True,
) -> StageSelectGUI:
    """Show the StageSelectGUI (or only build it, show=False) and map its outcome onto the WM_COPYDATA catalog:
    a confirm replies `stage_confirmed {typeId, stageId, amount, bonus, maxUnits}`,
    dismissal replies `stage_cancelled {}`. AHK does the energy math + confirm
    MsgBox on receiving the reply (that logic stays AHK-side)."""
    onConfirm, onCancel = _ReplyCallbacks(reply)
    window = StageSelectGUI(
        types,
        stages,
        defaults,
        onConfirm=onConfirm,
        onCancel=onCancel,
        config=config,
        placeholder=placeholder,
        energy=energy,
        preset=preset,
    )
    if show:
        window.ShowCentered()
    else:
        # built only to be reused: a window never shown is never closed, so it would stay registered
        EnterRouter.Instance().Unregister(window)
    return window
