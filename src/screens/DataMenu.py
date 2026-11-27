"""The Data menu: create a backup, restore one, open the backups folder and set the automatic backups.
Creating and restoring are app-side work (commons DataActions), sent through data.onDataAction."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox

from automaton_gui import Game as game_conf
from automaton_gui.I18n import T
from automaton_gui.screens.ConfigEditor import IniEditor
from automaton_gui.screens.SettingsSchema import BoolSetting, LabeledSection, NumberSetting

if TYPE_CHECKING:
    from automaton_gui.screens.ConfigMenu import ConfigMenuData

BACKUPS_SECTION = "Backups"
INTERVAL_MAX_HOURS = 24 * 30
KEEP_MAX = 100
# what the restore question answers
BACKUP_AND_RESTORE = "backup_and_restore"
RESTORE_ONLY = "restore_only"


def AddDataMenu(window, data: ConfigMenuData, openEditor: Callable[[Callable[[], object]], None]) -> None:
    strings = data.strings

    def Populate(menu) -> None:
        menu.addAction(T(strings, "data.create", "Create backup")).triggered.connect(
            lambda checked=False: _Send(data, "create")
        )
        menu.addAction(T(strings, "data.restore", "Restore backup...")).triggered.connect(
            lambda checked=False: RestoreBackup(window, data)
        )
        menu.addSeparator()
        menu.addAction(T(strings, "data.open_folder", "Open backups folder")).triggered.connect(
            lambda checked=False: _OpenFolder(data.backupsDir)
        )
        menu.addAction(T(strings, "data.auto_settings", "Automatic backups...")).triggered.connect(
            lambda checked=False: openEditor(lambda: BackupSettingsEditor(data, parent=window))
        )

    window.AddDynamicMenu(T(strings, "menu.data", "&Data"), Populate)


def RestoreBackup(window, data: ConfigMenuData) -> None:
    path = PickBackup(window, data)
    if path == "":
        return
    answer = AskBackupFirst(window, data.strings)
    if answer == "":
        return
    _Send(data, "restore", path, answer == BACKUP_AND_RESTORE)


# the dialogs are module functions so headless tests can replace them
def PickBackup(window, data: ConfigMenuData) -> str:
    path, _ = QFileDialog.getOpenFileName(
        window,
        T(data.strings, "data.restore_pick_title", "Restore a backup"),
        data.backupsDir,
        T(data.strings, "data.restore_filter", "Backups (*.zip)"),
    )
    return path


# BACKUP_AND_RESTORE, RESTORE_ONLY, or "" when cancelled
def AskBackupFirst(window, strings: dict) -> str:
    box = QMessageBox(window)
    box.setWindowTitle(T(strings, "data.restore_confirm_title", "Restore backup"))
    box.setText(T(strings, "data.restore_confirm",
                  "Restoring replaces your current settings and restarts the automaton. "
                  "Back up the current settings first?"))
    backupFirst = box.addButton(T(strings, "data.restore_backup_first", "Back up and restore"),
                                QMessageBox.ButtonRole.AcceptRole)
    restoreOnly = box.addButton(T(strings, "data.restore_only", "Restore only"), QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(backupFirst)
    box.exec()
    if box.clickedButton() is backupFirst:
        return BACKUP_AND_RESTORE
    if box.clickedButton() is restoreOnly:
        return RESTORE_ONLY
    return ""


def BackupSettingsEditor(data: ConfigMenuData, parent=None) -> IniEditor:
    strings = data.strings

    def Default(key: str) -> object:
        return game_conf.CONF.Default(BACKUPS_SECTION, key)

    section = LabeledSection(
        BACKUPS_SECTION,
        "",
        BoolSetting("backup_auto", T(strings, "data.backup_auto", "Back up automatically"),
                    default=Default("backup_auto")),
        NumberSetting("backup_interval_hours", T(strings, "data.backup_interval", "Hours between backups"),
                      default=Default("backup_interval_hours"), min=1, max=INTERVAL_MAX_HOURS),
        NumberSetting("backup_keep", T(strings, "data.backup_keep", "Automatic backups kept"),
                      default=Default("backup_keep"), min=1, max=KEEP_MAX,
                      help=T(strings, "data.backup_keep_help",
                             "Older automatic backups are deleted. Manual backups are never deleted.")),
    )
    return IniEditor(
        data.confFile,
        [section],
        columns=1,
        title=T(strings, "data.auto_settings_title", f"{game_conf.APP_NAME} | Automatic backups"),
        strings=strings,
        fit=True,
        onSave=lambda *_: _SettingsSaved(data),
        parent=parent,
    )


def _SettingsSaved(data: ConfigMenuData) -> None:
    if data.onSettingsSaved is not None:
        data.onSettingsSaved()


def _Send(data: ConfigMenuData, action: str, path: str = "", backupFirst: bool = False) -> None:
    if data.onDataAction is not None:
        data.onDataAction(action, path, backupFirst)


def _OpenFolder(folder: str) -> None:
    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
