from __future__ import annotations

from PySide6.QtWidgets import QWidget

from automaton_gui import Game as game_conf
from automaton_gui.screens.AccountManager import AccountManagerGUI
from automaton_gui.screens.ConfigEditor import IniEditor
from automaton_gui.screens.TeamSettings import TeamSettingsGUI
from automaton_gui.screens.wizard.WizardStep import StepPage, WizardStep

# one column: the wizard is narrower than the Hotkey settings window, two squeeze the key fields
KEYBINDS_COLUMNS = 1

# The steps that are one of the settings editors, embedded and pointed at the staged files.


class KeysStep(WizardStep):
    def Title(self) -> str:
        return self.ctx.T("wizard.keys.title", "Keybinds")

    def Build(self) -> QWidget:
        T = self.ctx.T
        self._editor = IniEditor(self.ctx.staging.conf, game_conf.KeybindsSchema(strings=self.ctx.strings),
                                 columns=KEYBINDS_COLUMNS, strings=self.ctx.strings, embedded=True)
        page, _ = StepPage(T("wizard.keys.heading", "Keybinds"),
                           T("wizard.keys.sub", "The defaults are filled in. Change any key that does not match "
                                                "your game, or leave them as they are."), self._editor)
        return page

    def Leave(self) -> bool:
        return self._editor.Commit()


class AccountsStep(WizardStep):
    def Title(self) -> str:
        return self.ctx.T("wizard.accounts.title", "Accounts")

    def Build(self) -> QWidget:
        T = self.ctx.T
        config = self.ctx.config
        groups = game_conf.AccountSchema(config.dailiesAreas, config.dailiesDefault, strings=self.ctx.strings)
        # the preset stage is picked from the launch window later, not during setup
        groups = [g for g in groups if not any((s.key == game_conf.PRESET_SKIP_KEY) for row in g.rows for s in row)]
        self._editor = AccountManagerGUI(self.ctx.staging.accounts, groups, strings=self.ctx.strings, embedded=True)
        page, _ = StepPage(T("wizard.accounts.heading", "Accounts"),
                           T("wizard.accounts.sub", "Add your accounts. The password is stored encrypted "
                                                    "for this Windows user only."), self._editor)
        return page

    def Leave(self) -> bool:
        return self._editor.Commit()


class TeamsStep(WizardStep):
    def Title(self) -> str:
        return self.ctx.T("wizard.teams.title", "Teams")

    def Build(self) -> QWidget:
        T = self.ctx.T
        self._editor = TeamSettingsGUI(self.ctx.staging.accounts, self.ctx.config.stageTeams,
                                       strings=self.ctx.strings, embedded=True)
        page, _ = StepPage(T("wizard.teams.heading", "Teams"),
                           T("wizard.teams.sub", "Tick the teams you have on each account. Having none is fine."),
                           self._editor)
        return page

    def Leave(self) -> bool:
        return self._editor.Commit()
