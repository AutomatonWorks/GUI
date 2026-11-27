from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QWidget

from automaton_gui import Game as game_conf
from automaton_gui.screens.AccountsFile import ExistingAccounts
from automaton_gui.screens.IniFile import IniRead
from automaton_gui.screens.wizard.EditorSteps import AccountsStep, KeysStep, TeamsStep
from automaton_gui.screens.wizard.GameStep import GAME_EXE_KEY, GENERAL, XXMI_ENABLED_KEY, XXMI_EXE_KEY, GameStep
from automaton_gui.screens.wizard.WizardStep import StepPage, WizardStep

GRID_MARGINS = (16, 12, 16, 12)
GRID_SPACING = (12, 10)


class SummaryStep(WizardStep):
    """One line per step with a way back to it; Finish is pressed here."""

    def __init__(self, ctx, goTo: Callable[[type], None], hasTeams: bool) -> None:
        super().__init__(ctx)
        self._goTo = goTo
        self._hasTeams = hasTeams

    def Title(self) -> str:
        return self.ctx.T("wizard.summary.title", "Summary")

    def Build(self) -> QWidget:
        T = self.ctx.T
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(box)
        grid.setContentsMargins(*GRID_MARGINS)
        grid.setHorizontalSpacing(GRID_SPACING[0])
        grid.setVerticalSpacing(GRID_SPACING[1])
        grid.setColumnStretch(1, 1)
        for row, (label, value, step) in enumerate(self._Rows()):
            name = QLabel(label)
            name.setProperty("subtle", True)
            grid.addWidget(name, row, 0)
            grid.addWidget(QLabel(value), row, 1)
            change = QPushButton(T("wizard.summary.change", "Change"))
            change.setFlat(True)
            change.clicked.connect(lambda _=False, target=step: self._goTo(target))
            grid.addWidget(change, row, 2)
        page, column = StepPage(T("wizard.summary.heading", "All set"),
                                T("wizard.summary.sub", "Press Finish to save everything and open the launch menu."))
        column.addSpacing(12)
        column.addWidget(box)
        column.addStretch(1)
        return page

    def _Rows(self) -> list[tuple[str, str, type]]:
        T = self.ctx.T
        conf = self.ctx.staging.conf
        notSet = T("wizard.summary.not_set", "Not set")
        rows = [(T("wizard.game.title", "Game"), IniRead(conf, GENERAL, GAME_EXE_KEY, "") or notSet, GameStep)]
        if self.ctx.modsId:
            xxmi = IniRead(conf, GENERAL, XXMI_EXE_KEY, "")
            if IniRead(conf, GENERAL, XXMI_ENABLED_KEY, "1") == "1":
                mods = T("wizard.summary.mods_on", "mods on")
            else:
                mods = T("wizard.summary.mods_off", "mods off")
            rows.append((T("wizard.summary.xxmi", "XXMI"), f"{xxmi} ({mods})" if xxmi else notSet, GameStep))
        changed = self._ChangedKeys()
        if changed:
            keys = T("wizard.summary.keys_changed", "Defaults, {count} changed", count=changed)
        else:
            keys = T("wizard.summary.keys_default", "Defaults")
        rows.append((T("wizard.keys.title", "Keybinds"), keys, KeysStep))
        accounts = len(ExistingAccounts(self.ctx.staging.accounts))
        if accounts == 1:
            accountsText = T("wizard.summary.account_one", "1 account defined")
        else:
            accountsText = T("wizard.summary.accounts", "{count} accounts defined", count=accounts)
        rows.append((T("wizard.accounts.title", "Accounts"), accountsText, AccountsStep))
        if self._hasTeams:
            teams = self._EnabledTeams()
            if teams == 1:
                teamsText = T("wizard.summary.team_one", "1 team enabled")
            else:
                teamsText = T("wizard.summary.teams", "{count} teams enabled", count=teams)
            rows.append((T("wizard.teams.title", "Teams"), teamsText, TeamsStep))
        return rows

    def _ChangedKeys(self) -> int:
        conf = self.ctx.staging.conf
        changed = 0
        for tab in game_conf.KeybindsSchema(strings=self.ctx.strings):
            for section in tab.sections:
                for s in section.settings:
                    if IniRead(conf, section.section, s.key, str(s.default)) != str(s.default):
                        changed += 1
        return changed

    def _EnabledTeams(self) -> int:
        accounts = self.ctx.staging.accounts
        teams = self.ctx.config.stageTeams.teams
        return sum(
            1 for section in ExistingAccounts(accounts) for team in teams
            if IniRead(accounts, section, team.enabledKey, "0").strip() == "1"
        )
