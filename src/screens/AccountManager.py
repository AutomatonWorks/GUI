from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automaton_gui.framework.Widgets import MakeButton
from automaton_gui.framework.Window import GuiApp
from automaton_gui.Game import DAILIES_AREA_DEFAULT, AccountSchema
from automaton_gui.I18n import T
from automaton_gui.screens.AccountForm import AccountForm
from automaton_gui.screens.AccountsFile import (
    ACCOUNT_PREFIX,
    MAX_ACCOUNT_ID,
    DisplayAccountName,
    ExistingAccounts,
)
from automaton_gui.screens.ConfCommon import ACCOUNTS_TITLE
from automaton_gui.screens.EditorFields import SettingFields
from automaton_gui.screens.FieldErrors import FieldErrors
from automaton_gui.screens.FieldRules import FieldRules
from automaton_gui.screens.FieldValues import FieldValues
from automaton_gui.screens.IniFile import DeleteSection, IniApply, IniRead
from automaton_gui.screens.SettingsSchema import Setting, SettingGroup, SettingType

# AccountManagerGUI ported from guis/AccountManagerGUI.ahk2: up to 10 accounts
# (indices 0-9) picked from a dropdown; the selected one's per-account game
# settings form (the AccountSchema the runtime reads) fills the window. Only one
# account is loaded at a time, so switching with unsaved edits asks Save / Discard /
# Cancel first. Account0 is permanent (no Remove). Add shows a new account that only
# reaches the file when it is saved; Remove changes the account set and rebuilds the
# dropdown.
#
# The fields come from the same engine as IniEditor (editor_fields, field_values,
# field_rules), so every schema flag works here too.
#
# Python stays dumb: the account schema arrives as constructor data (the dailies
# area list is AHK-derived and supplied in the payload), outcomes report through
# on_save()/on_cancel callbacks. Add account / Remove are handled wholly
# Python-side (they mutate the accounts file then rebuild), so they need no IPC.

MAX_ACCOUNTS = 10  # AccountSettings.MAX_COUNT
COUNTER_SECTION = "Accounts"
COUNTER_KEY = "nextId"
ACCOUNT0 = f"{ACCOUNT_PREFIX}0"

# ---- layout constants (edit these to restyle this screen) ----
BAR_MARGINS = (20, 12, 20, 12)
BAR_SPACING = 12
ACCOUNT_COMBO_MIN_WIDTH = 200


class AccountManagerGUI(AccountForm, SettingFields, FieldValues, FieldRules, FieldErrors, GuiApp):
    winWidth = 920
    winHeight = 700

    def __init__(
        self,
        file: str | Path,
        settings: list[SettingGroup],
        stageTypes: list | None = None,
        stageStages: dict | None = None,
        placeholder: str = "",
        selected: str = ACCOUNT0,
        strings: dict | None = None,
        onSave: Callable[[bool], None] | None = None,
        onCancel: Callable[[], None] | None = None,
        parent: QWidget | None = None,
        stageTeams=None,
        embedded: bool = False,
    ) -> None:
        self.file = str(file)
        self._settingDefs = list(settings)
        # The full StageType/Stage tables (same shape the launch window's own
        # picker uses) - the preset-stage button opens the same StageSelectGUI
        # picker from these.
        self._stageTypes = list(stageTypes or [])
        self._stageStages = {int(k): list(v) for k, v in (stageStages or {}).items()}
        self._placeholder = placeholder
        self._stageTeams = stageTeams
        self._section = selected
        self._onSave = onSave
        self._onCancel = onCancel
        self._saved = False
        # set once a switch or Add account saved edits without closing the window
        self._wroteChanges = False
        # an added account not saved yet: in the dropdown, not in the file
        self._pendingNew: str | None = None
        self.title = T(strings, "account.title", ACCOUNTS_TITLE)

        self.settings: dict[str, Setting] = {}          # "Section.key" -> Setting
        self._controls: dict[str, QWidget] = {}
        self._errors: dict[str, QLabel] = {}
        self._rowWidgets: dict[str, tuple[QLabel, QWidget]] = {}
        self._rowVisibility: dict[str, Callable[[bool], None]] = {}
        self._raw: dict[str, object] = {}
        self._baseline: dict[str, str] = {}
        self._presetButtons: dict[str, QPushButton] = {}  # section -> its stage button
        self._childEditors: list[GuiApp] = []
        super().__init__(parent, strings=strings, embedded=embedded)

    # no Theme menu (theming is the owner's job, as in AHK); just open the file
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

        self._top = self._TopBar()
        outer.addWidget(self._top)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, 1)
        self._bottom = self._BottomBar()
        self._bottom.setVisible(not self.embedded)
        outer.addWidget(self._bottom)
        self.setCentralWidget(central)

        self._FillAccountCombo(self._section)
        self._ShowAccount(self._accountCombo.currentData())

    def OnBuilt(self) -> None:
        self._RefreshSaveEnabled()
        self._RefreshAddEnabled()
        if not self.embedded:
            self._FitToForm()

    # Just big enough for the whole form so it never scrolls, unless the screen is smaller
    def _FitToForm(self) -> None:
        form = self._scroll.widget().sizeHint()
        frame = 2 * self._scroll.frameWidth()
        wantedWidth = max(self._top.sizeHint().width(), self._bottom.sizeHint().width(), form.width() + frame)
        wantedHeight = (self.menuBar().sizeHint().height() + self._top.sizeHint().height()
                         + form.height() + frame + self._bottom.sizeHint().height())
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            wantedWidth = min(wantedWidth, available.width())
            wantedHeight = min(wantedHeight, available.height())
        self.resize(wantedWidth, wantedHeight)

    def _TopBar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*BAR_MARGINS)
        row.setSpacing(BAR_SPACING)

        self._addBtn = MakeButton(self.T("account.add_account", "+  Add account"))
        self._addBtn.clicked.connect(self._AddAccount)
        self._accountCombo = QComboBox()
        self._accountCombo.setMinimumWidth(ACCOUNT_COMBO_MIN_WIDTH)
        self._accountCombo.currentIndexChanged.connect(self._OnAccountPicked)
        self._removeBtn = MakeButton(self.T("common.remove", "Remove"))
        self._removeBtn.clicked.connect(self._Remove)

        row.addWidget(QLabel(self.T("account.account_label", "Account")))
        row.addWidget(self._accountCombo)
        row.addWidget(self._addBtn)
        row.addWidget(self._removeBtn)
        row.addStretch(1)
        return bar

    def _BottomBar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*BAR_MARGINS)
        row.setSpacing(BAR_SPACING)
        cancel = MakeButton(self.T("common.cancel", "Cancel"))
        cancel.clicked.connect(self.close)
        self._saveBtn = MakeButton(self.T("common.save", "Save"), primary=True)
        self._saveBtn.clicked.connect(self.Save)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self._saveBtn)
        return bar

    # ---- account selection ----
    # Account0 is always present (a placeholder entry if the file has none yet) so
    # at least one account always exists.
    def _AccountSections(self) -> list[str]:
        accounts = ExistingAccounts(self.file)
        if ACCOUNT0 not in accounts:
            accounts.insert(0, ACCOUNT0)
        if self._pendingNew is not None:
            accounts.append(self._pendingNew)
        return accounts

    def _FillAccountCombo(self, section: str) -> None:
        combo = self._accountCombo
        combo.blockSignals(True)
        combo.clear()
        for account in self._AccountSections():
            combo.addItem(DisplayAccountName(self.file, account), account)
        combo.setCurrentIndex(max(combo.findData(section), 0))
        combo.blockSignals(False)

    def _OnAccountPicked(self, index: int) -> None:
        section = self._accountCombo.itemData(index)
        if section == self._section:
            return
        if not self._SettlePendingEdits():
            self._FillAccountCombo(self._section)
            return
        self._ReloadAccounts(section)  # a saved name change shows in the dropdown

    # Built from scratch for every account shown: the fields are loaded from the file,
    # so _rebuild carries the unsaved edits over itself.
    def _ShowAccount(self, section: str) -> None:
        self._section = section
        self.settings = {}
        self._controls = {}
        self._errors = {}
        self._rowWidgets = {}
        self._rowVisibility = {}
        self._raw = {}
        self._presetButtons = {}
        self._scroll.setWidget(self._AccountForm(section))  # deletes the old form
        for name, s in self.settings.items():
            self._LoadValue(name, s, IniRead(self.file, section, s.key, str(s.default)))
        self._WireRules()
        self._baseline = self._Snapshot()
        self._removeBtn.setEnabled(section != ACCOUNT0)
        self._RefreshSaveEnabled()

    # True when the shown account has no unsaved edits left: saved, discarded, or none.
    def _SettlePendingEdits(self) -> bool:
        if not self.IsDirty():
            return True
        choice = self._AskUnsavedSwitch()
        if choice == QMessageBox.StandardButton.Save:
            return self._WriteChanges()
        if choice == QMessageBox.StandardButton.Discard:
            if self._section == self._pendingNew:
                self._pendingNew = None
            else:
                self._ShowAccount(self._section)
            return True
        return False

    def _ReloadAccounts(self, section: str) -> None:
        self._FillAccountCombo(section)
        self._ShowAccount(self._accountCombo.currentData())
        self._RefreshAddEnabled()

    # The account set or a display name changed under the shown account: its unsaved edits stay.
    def _Rebuild(self) -> None:
        edits = self._ChangedValues()
        self._ReloadAccounts(self._section)
        for name, value in edits.items():
            if name in self.settings:
                self._LoadValue(name, self.settings[name], value)
        self._RefreshSaveEnabled()

    def _SwitchTo(self, section: str) -> None:
        if self._SettlePendingEdits():
            self._ReloadAccounts(section)
        else:
            self._Rebuild()

    # ---- actions ----
    def _Remove(self) -> None:
        section = self._section
        if not self._ConfirmRemove(section):
            return
        if section == self._pendingNew:
            self._pendingNew = None
        else:
            self._RetireId(int(section[len(ACCOUNT_PREFIX):]))
            DeleteSection(self.file, section)
        self._ReloadAccounts(ACCOUNT0)

    # The shown account's edits are settled first; the new one is written by its first Save.
    def _AddAccount(self) -> None:
        if not self._SettlePendingEdits():
            return
        accountId = self._NextAccountId()
        if accountId is None:
            self._Rebuild()
            return
        self._pendingNew = f"{ACCOUNT_PREFIX}{accountId}"
        self._ReloadAccounts(self._pendingNew)

    # Ids only go up: a removed account's id is never handed out again, so whatever is keyed
    # by it (its locks) can never end up on a different account.
    def _NextAccountId(self) -> int | None:
        if len(self._AccountSections()) >= MAX_ACCOUNTS:
            return None
        ids = [int(s[len(ACCOUNT_PREFIX):]) for s in self._AccountSections()]
        counter = int(IniRead(self.file, COUNTER_SECTION, COUNTER_KEY, "0") or 0)
        candidate = max([counter, *[i + 1 for i in ids]])
        return candidate if (candidate <= MAX_ACCOUNT_ID) else None

    def _RetireId(self, accountId: int) -> None:
        counter = int(IniRead(self.file, COUNTER_SECTION, COUNTER_KEY, "0") or 0)
        IniApply(self.file, {(COUNTER_SECTION, COUNTER_KEY): max(counter, accountId + 1)})

    def _RefreshAddEnabled(self) -> None:
        self._addBtn.setEnabled(self._NextAccountId() is not None)

    # ---- persistence ----
    # Save writes the changed fields of the shown account in one surgical pass and
    # closes. Closing/Escape/Cancel discards edits (warning first if dirty), matching
    # the IniEditor windows.
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
        self._ClearFieldErrors()
        if self.ShowFieldErrors(self._RequiredProblems()):
            return False
        changes = self._ChangedValues()
        if self._IsUnwritten():
            # the mail key is what marks the section as an account (ExistingAccounts)
            changes = {f"{self._section}.mail": "", **self._AllValues()}
            self._pendingNew = None
        if changes:
            IniApply(self.file, {tuple(name.split(".", 1)): value for name, value in changes.items()})
        self._baseline = self._Snapshot()
        self._wroteChanges = True
        return True

    # added and not saved yet, or the placeholder Account0 of a file without accounts
    def _IsUnwritten(self) -> bool:
        return (self._section == self._pendingNew) or (self._section not in ExistingAccounts(self.file))

    # every field, so a new account is written whole
    def _AllValues(self) -> dict[str, object]:
        values = self._ChangedValues()
        for name, s in self.settings.items():
            if (name not in values) and (s.type != SettingType.INFO) and not s.transient:
                values[name] = self.ValueOf(name)
        return values

    # a new account is unsaved until its first Save, even with every field left at its default
    def IsDirty(self) -> bool:
        return (self._section == self._pendingNew) or super().IsDirty()

    def OnEnter(self) -> None:
        self.Save()

    def OnClose(self) -> bool:
        if self._saved:
            return False
        if self.IsDirty() and not self._ConfirmDiscard():
            return True
        if self._wroteChanges and (self._onSave is not None):
            self._onSave()
        elif self._onCancel is not None:
            self._onCancel()
        return False

    # the dialogs are overridable so headless tests never hit a blocking modal (S9 gotcha)
    def _ConfirmDiscard(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.T("account.discard_confirm", "Discard unsaved changes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _AskUnsavedSwitch(self) -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self,
            self.windowTitle(),
            self.T("account.unsaved_switch", "Save your changes to {section}?", section=self._section),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _ConfirmRemove(self, section: str) -> bool:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.T(
                "account.remove_confirm", "Remove {section} and all its settings?", section=section
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


# ---- factory (callback-based; the channel adapter is S16) ---------------------


def AccountManagerEditor(
    file: str | Path,
    dailiesAreas: list | None = None,
    dailiesDefault: object = DAILIES_AREA_DEFAULT,
    stageTypes: list | None = None,
    stageStages: dict | None = None,
    placeholder: str = "",
    selected: str = ACCOUNT0,
    strings: dict | None = None,
    onSave: Callable[[bool], None] | None = None,
    onCancel: Callable[[], None] | None = None,
    parent: QWidget | None = None,
    stageTeams=None,
) -> AccountManagerGUI:
    areas = dailiesAreas or []
    settings = AccountSchema(areas, dailiesDefault, strings=strings)
    return AccountManagerGUI(
        file,
        settings,
        stageTypes=stageTypes,
        stageStages=stageStages,
        placeholder=placeholder,
        selected=selected,
        strings=strings,
        onSave=onSave,
        onCancel=onCancel,
        parent=parent,
        stageTeams=stageTeams,
    )
