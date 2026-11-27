from __future__ import annotations

from pathlib import Path
from typing import Callable

from automaton_gui.I18n import T
from automaton_gui.screens.AccountsFile import ACCOUNT_PREFIX, DisplayAccountName, ExistingAccounts
from automaton_gui.screens.ConfigEditor import IniEditor
from automaton_gui.screens.GameExe import ExeProblem

from automaton_gui import Game as game_conf
from automaton_gui.screens.SharedSettings import DevSection

# The generic parts of the two conf editors (ConfSchemas.ahk2's ConfSchema +
# KeybindSchema, ported onto the S9 IniEditor), everything that does not vary by game.
# general_schema/keybinds_schema/AccountSchema (the actual field lists) live in each game's own GameConf.py.

GENERAL_TITLE = f"{game_conf.APP_NAME} | General settings"
KEYBINDS_TITLE = f"{game_conf.APP_NAME} | Keybinds"
DEV_TITLE = f"{game_conf.APP_NAME} | Dev settings"
GAME_EXE_FIELD = "General.game_exe"


def GeneralEditor(
    file: str | Path,
    languages: list | None = None,
    languageDefault: object = "",
    launchModes: list | None = None,
    accountsFile: str | Path = "",
    strings: dict | None = None,
    onSave: Callable[[bool], None] | None = None,
    onCancel: Callable[[], None] | None = None,
    parent=None,
) -> IniEditor:
    accountChoices: list = []
    if accountsFile:
        accountChoices = [
            (section[len(ACCOUNT_PREFIX):], DisplayAccountName(accountsFile, section))
            for section in ExistingAccounts(accountsFile)
        ]
    schema = game_conf.GeneralSchema(
        languages or [],
        languageDefault,
        launchModes or [],
        accountChoices=accountChoices,
        strings=strings,
    )

    def CheckGameExe(editor: IniEditor) -> dict[str, str]:
        problem = ExeProblem(str(editor.ValueOf(GAME_EXE_FIELD)).strip(), strings, required=False,
                             names=game_conf.GAME_EXE_NAMES)
        return {GAME_EXE_FIELD: problem} if problem else {}

    return IniEditor(
        file,
        schema,
        columns=1,
        title=T(strings, "general_settings.title", GENERAL_TITLE),
        validate=CheckGameExe,
        strings=strings,
        onSave=onSave,
        onCancel=onCancel,
        parent=parent,
    )


def KeybindsEditor(
    file: str | Path,
    strings: dict | None = None,
    onSave: Callable[[bool], None] | None = None,
    onCancel: Callable[[], None] | None = None,
    parent=None,
) -> IniEditor:
    return IniEditor(
        file,
        game_conf.KeybindsSchema(strings=strings),
        columns=2,
        title=T(strings, "keybinds.title", KEYBINDS_TITLE),
        strings=strings,
        onSave=onSave,
        onCancel=onCancel,
        fit=True,
        parent=parent,
    )


def DevEditor(
    file: str | Path,
    strings: dict | None = None,
    onSave: Callable[[bool], None] | None = None,
    onCancel: Callable[[], None] | None = None,
    parent=None,
) -> IniEditor:
    return IniEditor(
        file,
        [DevSection(game_conf.CONF, strings, getattr(game_conf, "DEV_ROWS", ()))],
        columns=1,
        title=T(strings, "dev.title", DEV_TITLE),
        strings=strings,
        fit=True,
        onSave=onSave,
        onCancel=onCancel,
        parent=parent,
    )


# ---- Account game-settings schema (per-account [AccountN] fields) ------------
#
# Ported from _AccountGameSettings() in guis/ConfSchemas.ahk2. The per-account
# game settings (coffee, dailies area, promoter, training target, team presets,
# mindscapes) the runtime reads from each [AccountN] section. AccountManagerGUI
# (S12) renders one of these forms per account inside its accordion.
#
# The dailies-area dropdown is AHK-derived dynamic data (DailiesArea.Choices(),
# localized). Python stays dumb: it arrives in the show_editor payload, same as
# the General language/launch-mode lists.

ACCOUNTS_TITLE = f"{game_conf.APP_NAME} | Account settings"
