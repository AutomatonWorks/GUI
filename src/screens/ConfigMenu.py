from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from automaton_gui.I18n import T
from automaton_gui.screens.AccountManager import AccountManagerEditor
from automaton_gui.screens.ClipboardCopy import CopyLastRunLog
from automaton_gui.screens.ConfCommon import (
    DevEditor,
    GeneralEditor,
    KeybindsEditor,
)
from automaton_gui.screens.DataMenu import AddDataMenu
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.LockMenu import ActiveAccount, PopulateLocksMenu
from automaton_gui.screens.StageTeam import ActiveAccountSection
from automaton_gui.screens.TeamSettings import TeamSettingsGUI
from automaton_gui.theme import Palettes


def _ReadSavedTheme(confFile: str) -> str | None:
    """The saved palette from [General] theme= in the conf, or None if absent /
    unknown. Theme persistence lives in Python now (AHK has no GUI), so the GUI
    reads + writes theme= itself instead of going over the bridge."""
    if not confFile:
        return None
    raw = IniRead(confFile, "General", "theme")
    return raw if raw and Palettes.Has(raw) else None


def _PersistTheme(confFile: str, mode: str) -> None:
    if confFile:
        IniApply(confFile, {("General", "theme"): mode})

# The shared menu bar ported from guis/ZzzGui.ahk2 Menu(). Every old AHK GUI
# carried this bar; in the Python port the user only reaches it from the two
# entry windows - LaunchGUI (startup) and MacroMenu (Home) - so it lives there and
# nowhere else (the editors themselves keep just "open file externally").
#
# The editors are all Python and open IN-PROCESS as children of the host window;
# no IPC round-trip to open one. The AHK-derived dropdown data (languages, launch
# modes, dailies areas) and the config file paths arrive in the
# show_launch / show_macro payload (Python stays dumb). Two outcomes are app-side
# effects, so they report back through plain callbacks wired to GuiBridge
# notifications (the window never imports the bridge):
#   - a saved settings window                         -> on_settings_saved (AppBootstrap.apply_settings)
#   - the Locks actions                                 -> on_lock_action(action, which, account, value)
#   - the Data actions                                  -> on_data_action(action, path, backup_first)


@dataclass
class ConfigMenuData:
    confFile: str
    savFile: str
    accountsFile: str = ""  # "" -> no Account settings item (file absent AHK-side)
    logFile: str = ""
    repoUrl: str = ""
    languages: list = field(default_factory=list)
    languageDefault: object = ""
    launchModes: list = field(default_factory=list)
    dailiesAreas: list = field(default_factory=list)
    dailiesDefault: object = 0
    # The ZZZ stage DB (StageType/Stage instances from stageSelect.py), full
    # detail - reused as-is by the launch window's "Change..." picker and
    # reduced to id+name pairs by the account editor's two dropdowns.
    stageTypes: list = field(default_factory=list)
    stageStages: dict = field(default_factory=dict)
    # the game's logo (StageSelectHooks.PlaceholderImage) for the "Change..." picker's unselected slot -
    # The stage picker's art until a stage is picked.
    placeholder: str = ""
    # The stage picker's teams (stage_team.StageTeamsConfig); None when the game has none.
    stageTeams: object = None
    # The lock catalog (LockCore.CatalogJson) and the Locks.json it is stored in; the menu reads the
    # active account's state from the file every time it opens.
    locks: list = field(default_factory=list)
    locksFile: str = ""
    strings: dict = field(default_factory=dict)
    onSettingsSaved: Callable[[], None] | None = None
    # The folder the backups go to; "" -> no Data menu.
    backupsDir: str = ""
    onLockAction: Callable[[str, str, str, str], None] | None = None
    onDataAction: Callable[[str, str, bool], None] | None = None


def BuildConfigMenus(window, data: ConfigMenuData) -> None:
    """Build the shared menu bar (Configuration / Locks / Data / Theme / Help) on
    `window`, in the same order the old AHK GUI framework used. Opened editors are kept on
    `window._configEditors` so Python's GC does not close them the moment the
    menu handler returns (same pattern as AccountManagerGUI's child editors)."""
    window._configEditors = []
    _AddConfigurationMenu(window, data)
    if data.locks:
        _AddLocksMenu(window, data)
    if data.backupsDir:
        AddDataMenu(window, data, lambda factory: _OpenEditor(window, factory))
    _AddThemeMenu(window, data)
    _AddHelpMenu(window, data)


def _OpenEditor(window, factory: Callable[[], object]) -> None:
    editor = factory()
    window._configEditors.append(editor)
    editor.ShowCentered()


# The app applies the saved values in place (hotkeys, log level, console, game keys).
def _SettingsSaved(data: ConfigMenuData) -> None:
    if data.onSettingsSaved is not None:
        data.onSettingsSaved()


# activeAccount now has its own dropdown here too - the launch window's
# account combo was built once at window-open time, so it needs telling
# after a General settings save or it'd keep showing the old selection.
def _GeneralSettingsSaved(window, data: ConfigMenuData) -> None:
    _SettingsSaved(data)
    sync = getattr(window, "_SyncAccountCombo", None)
    if sync is not None:
        sync()


# Account and Team settings apply on their own (AccountSettings.Read() is always
# fresh), but the launch window's own preset-stage button/checkbox were
# read at build time and go stale the moment this save changes them -
# refresh them live rather than leaving "not set" on screen next to an
# account settings panel that just showed the opposite. The macro menu
# also hides buttons and locks per account, so it asks AHK to rebuild them too.
def _AccountSettingsSaved(window) -> None:
    reopen = getattr(window, "RequestRefresh", None)
    if reopen is not None:
        reopen()
    refresh = getattr(window, "_RefreshPresetRow", None)
    if refresh is not None:
        refresh()


def _ConfigurationItems(window, data: ConfigMenuData) -> list[dict]:
    strings = data.strings
    items = [{
        "name": T(strings, "config_menu.general_settings", "General settings"),
        "factory": lambda: GeneralEditor(
            data.confFile,
            languages=data.languages,
            languageDefault=data.languageDefault,
            launchModes=data.launchModes,
            accountsFile=data.accountsFile,
            strings=strings,
            onSave=lambda: _GeneralSettingsSaved(window, data),
            parent=window,
        ),
    }]
    if data.accountsFile:
        items.append({
            "name": T(strings, "config_menu.account_settings", "Account settings"),
            "factory": lambda: AccountManagerEditor(
                data.accountsFile,
                dailiesAreas=data.dailiesAreas,
                dailiesDefault=data.dailiesDefault,
                stageTypes=data.stageTypes,
                stageStages=data.stageStages,
                placeholder=data.placeholder,
                selected=ActiveAccountSection(data.confFile),
                strings=strings,
                onSave=lambda: _AccountSettingsSaved(window),
                parent=window,
                stageTeams=data.stageTeams,
            ),
        })
    if data.accountsFile and data.stageTeams and data.stageTeams.teams:
        items.append({
            "name": T(strings, "config_menu.team_settings", "Team settings"),
            "factory": lambda: TeamSettingsGUI(
                data.accountsFile,
                data.stageTeams,
                account=ActiveAccountSection(data.confFile),
                strings=strings,
                onSave=lambda: _AccountSettingsSaved(window),
                parent=window,
            ),
        })
    items.append({
        "name": T(strings, "config_menu.hotkey_settings", "Hotkey settings"),
        "factory": lambda: KeybindsEditor(
            data.confFile, strings=strings, onSave=lambda: _SettingsSaved(data), parent=window
        ),
    })
    return items


def _DevMode(data: ConfigMenuData) -> bool:
    return IniRead(data.confFile, "Dev", "Dev", "0").strip() == "1"


def _AddConfigurationMenu(window, data: ConfigMenuData) -> None:
    strings = data.strings
    items = _ConfigurationItems(window, data)
    devItem = {
        "name": T(strings, "config_menu.dev_settings", "Dev settings"),
        "factory": lambda: DevEditor(
            data.confFile, strings=strings, onSave=lambda: _SettingsSaved(data), parent=window
        ),
    }

    def Populate(menu) -> None:
        for item in items + ([devItem] if _DevMode(data) else []):
            menu.addAction(item["name"]).triggered.connect(
                lambda checked=False, factory=item["factory"]: _OpenEditor(window, factory)
            )

    window.AddDynamicMenu(T(strings, "menu.configuration", "&Configuration"), Populate)


def _AddLocksMenu(window, data: ConfigMenuData) -> None:
    def Send(action: str, which: str, value: str = "") -> None:
        if data.onLockAction is not None:
            data.onLockAction(action, which, ActiveAccount(data.confFile), value)

    window.AddDynamicMenu(
        T(data.strings, "menu.locks", "&Locks"),
        lambda menu: PopulateLocksMenu(menu, data, data.strings, Send),
    )


def _AddThemeMenu(window, data: ConfigMenuData) -> None:
    window.AddThemeMenu()
    saved = _ReadSavedTheme(data.confFile)
    if saved is not None:
        window.SetTheme(saved)
    window._onThemeChange = lambda mode: _PersistTheme(data.confFile, mode)


def _AddHelpMenu(window, data: ConfigMenuData) -> None:
    strings = data.strings

    def Populate(menu) -> None:
        menu.addAction(T(strings, "config_menu.github_repo", "GitHub repository")).triggered.connect(
            lambda checked=False: _OpenUrl(data.repoUrl)
        )
        menu.addAction(T(strings, "config_menu.open_log_file", "Open log file")).triggered.connect(
            lambda checked=False: _OpenFile(data.logFile)
        )
        if _DevMode(data):
            menu.addAction(T(strings, "config_menu.copy_log", "Copy current log")).triggered.connect(
                lambda checked=False: CopyLastRunLog(window, data.logFile, strings)
            )

    window.AddDynamicMenu(T(strings, "menu.help", "&Help"), Populate)


def _OpenUrl(url: str) -> None:
    if url:
        QDesktopServices.openUrl(QUrl(url))


def _OpenFile(path: str) -> None:
    if path:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
