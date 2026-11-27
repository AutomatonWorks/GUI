from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.ErrorBubble import ErrorBubble
from automaton_gui.framework.Widgets import MakeButton
from automaton_gui.framework.Window import GuiApp
from automaton_gui.I18n import T
from automaton_gui.screens.AccountsFile import ACCOUNT_PREFIX, DisplayAccountName, ExistingAccounts
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.StageTeam import StageTeamsConfig
from automaton_gui.screens.TeamCard import TeamSettingsCard

# Every team of one account at once: which ones the account has, their squad preset
# slots, the shared per-character mindscapes and the default team. Edits stay in the
# window until Save, which writes the shown account in one pass.

WIN_WIDTH = 900
WIN_HEIGHT = 760
BAR_MARGINS = (20, 12, 20, 12)
BAR_SPACING = gc.SPACING_ROW
GRID_MARGINS = (20, 8, 20, 8)
GRID_SPACING = 14
GRID_COLUMNS = 2
ACCOUNT_COMBO_WIDTH = 260
DEFAULT_COMBO_WIDTH = 300

SWITCH_SAVE = "save"
SWITCH_DISCARD = "discard"
SWITCH_CANCEL = "cancel"


class TeamSettingsGUI(GuiApp):
    winWidth = WIN_WIDTH
    winHeight = WIN_HEIGHT

    def __init__(
        self,
        file: str | Path,
        config: StageTeamsConfig,
        account: str = "",
        strings: dict | None = None,
        onSave: Callable[[], None] | None = None,
        parent: QWidget | None = None,
        embedded: bool = False,
    ) -> None:
        self.file = str(file)
        self._config = config
        self._accounts = ExistingAccounts(self.file) or [f"{ACCOUNT_PREFIX}0"]
        self._section = account if account in self._accounts else self._accounts[0]
        self._onSave = onSave
        self._saved = False
        self._wroteChanges = False
        self._cards: list[TeamSettingsCard] = []
        self._baseline: tuple = ()
        self.title = T(strings, "team_settings.title", "Team settings")
        super().__init__(parent, strings=strings, embedded=embedded)

    def Menu(self) -> None:
        self.AddConfigMenu(
            self.T("menu.file", "&File"),
            [{"name": self.T("common.open_file_externally", "Open file externally"), "path": self.file}],
        )

    # ---- build ----
    def Build(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._AccountBar())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._CardGrid())
        outer.addWidget(scroll, 1)
        outer.addWidget(self._BottomBar())
        self.setCentralWidget(central)

    def OnBuilt(self) -> None:
        self._LoadAccount()

    def _AccountBar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*BAR_MARGINS)
        row.setSpacing(BAR_SPACING)
        row.addWidget(QLabel(self.T("team_settings.account", "Account")))
        self._accountCombo = QComboBox()
        self._accountCombo.setFixedWidth(ACCOUNT_COMBO_WIDTH)
        for section in self._accounts:
            self._accountCombo.addItem(DisplayAccountName(self.file, section), section)
        self._accountCombo.setCurrentIndex(self._accounts.index(self._section))
        self._accountCombo.currentIndexChanged.connect(self._AccountPicked)
        row.addWidget(self._accountCombo)
        row.addStretch(1)
        return bar

    def _CardGrid(self) -> QWidget:
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(*GRID_MARGINS)
        grid.setSpacing(GRID_SPACING)
        for index, team in enumerate(self._config.teams):
            card = TeamSettingsCard(team, self.T)
            card.have.toggled.connect(self._TeamToggled)
            card.slot.valueChanged.connect(self._RefreshSaveEnabled)
            if card.mindscape is not None:
                card.mindscape.valueChanged.connect(
                    lambda value, source=card: self._SyncMindscape(source, value))
            self._cards.append(card)
            grid.addWidget(card, index // GRID_COLUMNS, index % GRID_COLUMNS)
        for column in range(GRID_COLUMNS):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch(grid.rowCount(), 1)
        return content

    def _BottomBar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*BAR_MARGINS)
        row.setSpacing(BAR_SPACING)
        row.addWidget(QLabel(self.T("team_settings.default_team", "Default team used")))
        self._defaultCombo = QComboBox()
        self._defaultCombo.setFixedWidth(DEFAULT_COMBO_WIDTH)
        self._defaultCombo.currentIndexChanged.connect(self._RefreshSaveEnabled)
        row.addWidget(self._defaultCombo)
        self._defaultError = ErrorBubble(self._defaultCombo)
        row.addStretch(1)
        cancel = MakeButton(self.T("common.cancel", "Cancel"))
        cancel.clicked.connect(self.close)
        row.addWidget(cancel)
        self._saveBtn = MakeButton(self.T("common.save", "Save"), primary=True)
        self._saveBtn.clicked.connect(self.Save)
        row.addWidget(self._saveBtn)
        # an embedded page is saved by its host (Commit)
        cancel.setVisible(not self.embedded)
        self._saveBtn.setVisible(not self.embedded)
        return bar

    # ---- account data ----
    def _Read(self, key: str) -> int:
        value = IniRead(self.file, self._section, key, "0").strip() if key else "0"
        return int(value) if value.isdigit() else 0

    def _LoadAccount(self) -> None:
        for card in self._cards:
            team = card.team
            card.Load(self._Read(team.enabledKey) == 1, self._Read(team.slotKey), self._Read(team.mindscapeKey))
        self._RefreshDefaultTeams(self._Read(self._config.defaultKey))
        self._baseline = self._Snapshot()
        self._RefreshSaveEnabled()

    def _Snapshot(self) -> tuple:
        return tuple(card.State() for card in self._cards), self._DefaultTeam()

    def IsDirty(self) -> bool:
        return self._Snapshot() != self._baseline

    def _DefaultTeam(self) -> int:
        teamID = self._defaultCombo.currentData()
        return 0 if teamID is None else teamID

    def _Updates(self) -> dict[tuple[str, str], object]:
        section = self._section
        updates: dict[tuple[str, str], object] = {}
        for card in self._cards:
            have, slot, mindscape = card.State()
            updates[(section, card.team.enabledKey)] = 1 if have else 0
            if have:
                updates[(section, card.team.slotKey)] = slot
            if mindscape is not None:
                updates[(section, card.team.mindscapeKey)] = mindscape
        updates[(section, self._config.defaultKey)] = self._DefaultTeam()
        return updates

    # ---- live sync ----
    def _TeamToggled(self, _checked: bool) -> None:
        self._RefreshDefaultTeams(self._DefaultTeam())
        self._RefreshSaveEnabled()

    def _RefreshDefaultTeams(self, selected: int) -> None:
        checked = [card for card in self._cards if card.IsChecked()]
        combo = self._defaultCombo
        combo.blockSignals(True)
        combo.clear()
        for card in checked:
            combo.addItem(card.Label(), card.team.id)
        combo.setCurrentIndex(combo.findData(selected))
        combo.setEnabled(bool(checked))
        combo.blockSignals(False)

    def _SyncMindscape(self, source: TeamSettingsCard, value: int) -> None:
        for card in self._cards:
            if (card is not source) and (card.team.mindscapeKey == source.team.mindscapeKey):
                card.mindscape.blockSignals(True)
                card.mindscape.setValue(value)
                card.mindscape.blockSignals(False)
                card.ShowMindscape(value)
        self._RefreshDefaultTeams(self._DefaultTeam())
        self._RefreshSaveEnabled()

    def _CanSave(self) -> bool:
        noTeam = not any(card.IsChecked() for card in self._cards)
        return noTeam or (self._DefaultTeam() != 0)

    def _RefreshSaveEnabled(self, *_) -> None:
        self._defaultError.hide()
        self._saveBtn.setEnabled(self._CanSave())

    # ---- account switch ----
    def _AccountPicked(self, index: int) -> None:
        section = self._accountCombo.itemData(index)
        if self.IsDirty():
            choice = self._ConfirmSwitch()
            if (choice == SWITCH_CANCEL) or ((choice == SWITCH_SAVE) and not self._WriteChanges()):
                self._RestoreAccountCombo()
                return
        self._section = section
        self._LoadAccount()

    def _RestoreAccountCombo(self) -> None:
        self._accountCombo.blockSignals(True)
        self._accountCombo.setCurrentIndex(self._accounts.index(self._section))
        self._accountCombo.blockSignals(False)

    # ---- persistence ----
    def Save(self, *_) -> None:
        if not self._WriteChanges():
            return
        self._saved = True
        if self._onSave is not None:
            self._onSave()
        self.close()

    # the embedded page's save: writes the shown account and stays open
    def Commit(self) -> bool:
        return self._WriteChanges()

    def _WriteChanges(self) -> bool:
        if not self._CanSave():
            self._defaultError.ShowMessage(self.T("team_settings.pick_default", "Pick the default team."))
            self._defaultCombo.setFocus()
            return False
        IniApply(self.file, self._Updates())
        self._baseline = self._Snapshot()
        self._wroteChanges = True
        return True

    def OnEnter(self) -> None:
        self.Save()

    def OnClose(self) -> bool:
        if self._saved:
            return False
        if self.IsDirty() and not self._ConfirmDiscard():
            return True
        if self._wroteChanges and (self._onSave is not None):
            self._onSave()
        return False

    # the dialogs are overridable so headless tests never hit a blocking modal
    def _ConfirmDiscard(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.T("team_settings.discard_confirm", "Discard unsaved changes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _ConfirmSwitch(self) -> str:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.T("team_settings.switch_confirm", "Save your changes to this account before switching?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return SWITCH_SAVE
        if answer == QMessageBox.StandardButton.Discard:
            return SWITCH_DISCARD
        return SWITCH_CANCEL
