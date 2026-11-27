from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.PresetRow import NarrowCombo
from automaton_gui.screens.StageTeam import ActiveAccountSection

# The "Default team used" row of the launch and macro windows: a label and a
# team dropdown on their own centred row under the account row.
TEAM_ROW_SPACING = gc.SPACING_ROW
TEAM_LABEL_FONT_SIZE = gc.APP_FONT_POINT_SIZE
TEAM_COMBO_FONT_SIZE = gc.APP_FONT_POINT_SIZE


def TeamComboRow(labelText: str, combo: QComboBox) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(TEAM_ROW_SPACING)
    row.addStretch(1)
    label = QLabel(labelText)
    ApplyFont(label, TEAM_LABEL_FONT_SIZE)
    row.addWidget(label)
    NarrowCombo(combo, gc.TEAM_COMBO_WIDTH)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    ApplyFont(combo, TEAM_COMBO_FONT_SIZE)
    row.addWidget(combo)
    row.addStretch(1)
    return row


class DefaultTeamRowMixin:
    """Launch and macro row editing the active account's DefaultTeam from its enabled teams.
    Writes Accounts.ini directly, like the preset stage button. Needs `self._config` on the host."""

    _defaultTeamCombo: QComboBox | None = None

    def _DefaultTeamRow(self) -> QHBoxLayout | None:
        cfg = self._config
        if cfg is None or not cfg.accountsFile or not cfg.stageTeams or not cfg.stageTeams.defaultKey:
            return None
        combo = QComboBox()
        combo.currentIndexChanged.connect(self._DefaultTeamPicked)
        self._defaultTeamCombo = combo
        self._ReloadDefaultTeam()
        return TeamComboRow(self.T("default_team.label", "Default team used"), combo)

    def _ReloadDefaultTeam(self) -> None:
        combo = self._defaultTeamCombo
        if combo is None:
            return
        cfg = self._config
        section = ActiveAccountSection(cfg.confFile)
        enabled = [
            team for team in cfg.stageTeams.teams
            if IniRead(cfg.accountsFile, section, team.enabledKey, "0").strip() == "1"
        ]
        current = IniRead(cfg.accountsFile, section, cfg.stageTeams.defaultKey, "0").strip()
        combo.blockSignals(True)
        combo.clear()
        combo.setEnabled(bool(enabled))
        if enabled:
            for team in enabled:
                combo.addItem(team.label, team.id)
            combo.setCurrentIndex(combo.findData(int(current)) if current.isdigit() else -1)
        else:
            combo.addItem(self.T("default_team.none", "No team enabled"))
        combo.blockSignals(False)
        if enabled and (combo.currentIndex() >= 0):
            self._DefaultTeamChosen(combo.currentData())

    def _DefaultTeamPicked(self, index: int) -> None:
        if index < 0:
            return
        cfg = self._config
        section = ActiveAccountSection(cfg.confFile)
        teamID = self._defaultTeamCombo.itemData(index)
        IniApply(cfg.accountsFile, {(section, cfg.stageTeams.defaultKey): teamID})
        self._DefaultTeamChosen(teamID)

    def _DefaultTeamChosen(self, teamID: int) -> None:
        """Hook for a host that also reports the team elsewhere."""
