from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automaton_gui import Game as game_conf
from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import BADGE_GAP, ApplyFont, PaintBadge, Separator
from automaton_gui.framework.Window import GuiApp
from automaton_gui.Game import PRESET_SKIP_KEY, PRESET_TYPE_KEY
from automaton_gui.I18n import T
from automaton_gui.ipc import Reply
from automaton_gui.screens.DefaultTeamRow import DefaultTeamRowMixin, TeamComboRow
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.PresetRow import PresetRowMixin
from automaton_gui.theme.Palettes import HexOf
from automaton_gui.theme.Theme import theme

# ---- layout constants (edit these to restyle this screen) ----
ROOT_MARGINS = (gc.MARGIN_SCREEN_SIDE, 24, gc.MARGIN_SCREEN_SIDE, 30)
ROOT_SPACING = gc.SPACING_SCREEN
HEADING_FONT_SIZE = 32
SUBTITLE_FONT_SIZE = gc.APP_FONT_POINT_SIZE
LAUNCH_BUTTON_MIN_HEIGHT = 60
LAUNCH_BUTTON_FONT_SIZE = 15

# LaunchGUI ported from guis/LaunchGUI.ahk2: the launch-mode picker. A big title,
# a "click to pick" hint, a team-preset dropdown, and a 1-column grid of flat
# launch-mode buttons (single-click selects, hover shows the help tip).
#
# Python stays dumb: the launch options and team presets arrive as constructor
# data (closures/IPC payload supply them), never read from the AHK side here.
# Selection / dismissal / team change report out through callbacks so the IPC
# glue (OpenLaunchGui) maps them to the WM_COPYDATA catalog without the window
# knowing the channel exists.


@dataclass(frozen=True)
class LaunchItem:
    id: int
    label: str
    tip: str = ""
    # True for the preset launch modes (LaunchOption.PRESET_AUTO/OUTPOSTS) -
    # AHK sets this, Python never hardcodes the numeric mode ids (see _select).
    preset: bool = False
    badge: str = ""  # drop-bonus pill ("x2"/"x3"), empty for none


@dataclass(frozen=True)
class TeamItem:
    id: int
    label: str


class _BadgeButton(QPushButton):
    """Paints the badge after the centred label, so text() stays the plain label."""

    def __init__(self, text: str, badge: str) -> None:
        super().__init__(text)
        self._badge = badge

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        left = (self.width() + self.fontMetrics().horizontalAdvance(self.text())) / 2 + BADGE_GAP
        painter = QPainter(self)
        PaintBadge(painter, left, self.height() / 2, self._badge, QColor(HexOf(theme.palette.accent)),
                    self.font())
        painter.end()


class LaunchGUI(PresetRowMixin, DefaultTeamRowMixin, GuiApp):
    winWidth = 700
    winHeight = 760

    def __init__(
        self,
        options: list[LaunchItem],
        teams: list[TeamItem] | None = None,
        currentTeam: int | None = None,
        onSelect: Callable[[int], None] | None = None,
        onTeamChange: Callable[[int], None] | None = None,
        onCancel: Callable[[], None] | None = None,
        config=None,
        parent: QWidget | None = None,
    ) -> None:
        self._options = list(options)
        self._teams = list(teams or [])
        self._currentTeam = currentTeam
        self._onSelect = onSelect
        self._onTeamChange = onTeamChange
        self._onCancel = onCancel
        self._config = config
        self._confirmed = False
        self._buttons: list[QPushButton] = []
        self._teamCombo: QComboBox | None = None
        self.title = T(
            config.strings if config else None, "launch.title", f"{game_conf.APP_NAME} | Launch Options"
        )
        super().__init__(parent, strings=config.strings if config else None)

    # The shared config menu bar (ported from ZzzGui.Menu) lives on this entry
    # window; build it when the host supplied the config data, else just the
    # base Theme menu (the payload-less preview/manual-poke path).
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

        heading = QLabel(self.T("launch.heading", game_conf.APP_NAME))
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ApplyFont(heading, HEADING_FONT_SIZE, bold=True)
        root.addWidget(heading)

        subtitle = QLabel(self.T("launch.subtitle", "Click a button to select a launch mode"))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setProperty("subtle", True)
        ApplyFont(subtitle, SUBTITLE_FONT_SIZE)
        root.addWidget(subtitle)

        root.addWidget(Separator())

        presetRow = self._PresetRow()
        drewShortcut = presetRow is not None
        if presetRow is not None:
            root.addLayout(presetRow)

        teamRow = self._DefaultTeamRow()
        if teamRow is not None:
            self._teamCombo = self._defaultTeamCombo
        elif self._teams:
            teamRow = self._TeamRow()
        if teamRow is not None:
            root.addLayout(teamRow)
            drewShortcut = True

        if drewShortcut:
            root.addWidget(Separator())

        for item in self._options:
            button = _BadgeButton(item.label, item.badge) if item.badge else QPushButton(item.label)
            if item.tip:
                button.setToolTip(item.tip)
            button.setMinimumHeight(LAUNCH_BUTTON_MIN_HEIGHT)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            ApplyFont(button, LAUNCH_BUTTON_FONT_SIZE)
            button.clicked.connect(lambda checked=False, mode=item.id: self._Select(mode))
            self._buttons.append(button)
            root.addWidget(button, 1)

        self.setCentralWidget(central)

    # A preset-mode click (Do dailies and battery / Do everything) picks its
    # stage IN this still-open window before replying at all: replying is
    # what unblocks AHK's ShowLaunchGui() request and closes this window, so
    # doing that first and picking the stage second would mean a cancelled
    # picker leaves nothing on screen. Only once a stage is actually
    # confirmed - or the account already has one and opted out of asking -
    # does the window close and the reply go out.
    def _Select(self, mode: int) -> None:
        item = next((o for o in self._options if o.id == mode), None)
        if item is not None and item.preset and not self._PresetReadyToLaunch():
            self._PickPresetStageThen(mode)
            return
        self._ConfirmAndClose(mode)

    def _ConfirmAndClose(self, mode: int) -> None:
        self._confirmed = True
        if self._onSelect is not None:
            self._onSelect(mode)
        self.close()

    def _TeamChanged(self, index: int) -> None:
        if index < 0 or self._teamCombo is None:
            return
        self._DefaultTeamChosen(self._teamCombo.itemData(index))

    def _DefaultTeamChosen(self, teamID: int) -> None:
        if self._onTeamChange is not None:
            self._onTeamChange(teamID)

    def _RefreshPresetRow(self) -> None:
        super()._RefreshPresetRow()
        self._ReloadDefaultTeam()

    # ---- team row without Team settings data (payload teams only) --------
    def _TeamRow(self) -> QHBoxLayout:
        combo = QComboBox()
        for team in self._teams:
            combo.addItem(team.label, team.id)
        if self._currentTeam is not None:
            index = next(
                (i for i, t in enumerate(self._teams) if t.id == self._currentTeam), 0)
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(self._TeamChanged)
        self._teamCombo = combo
        return TeamComboRow(self.T("default_team.label", "Default team used"), combo)

    def _PresetReadyToLaunch(self) -> bool:
        """Mirrors PresetStageChosen's own SkipSelect check on the AHK side:
        if the account opted out of the picker and already has a stage
        configured, a preset-mode click goes straight through - no in-process
        pick needed, matching AHK's bypass for a remote dispatch."""
        section = self._CurrentAccountSection()
        if section is None:
            return True  # no accounts file - AHK's own DecideLaunch handles it
        accountsFile = self._config.accountsFile
        skip = IniRead(accountsFile, section, PRESET_SKIP_KEY, "0").strip() == "1"
        typeID = int(IniRead(accountsFile, section, PRESET_TYPE_KEY, "0") or 0)
        return skip and bool(typeID)

    def _PickPresetStageThen(self, mode: int) -> None:
        section = self._CurrentAccountSection()
        if section is None:
            self._ConfirmAndClose(mode)
            return

        def OnPicked(_typeID: int, _stageID: int) -> None:
            self._RefreshPresetRow()
            # One-shot: tells DecideLaunch the stage for THIS dispatch was
            # already resolved here, so it must not open its own picker too.
            IniApply(self._config.confFile, {("General", "localStageChosen"): 1})
            self._ConfirmAndClose(mode)

        self._presetPicker = self._BuildPresetPicker(section, OnPicked)
        self._presetPicker.ShowCentered()

    # Dismissing without a pick (Escape, X) means cancel. The AHK window called
    # ExitApp here; in the split architecture Python only reports it - AHK owns
    # the exit decision.
    def OnClose(self) -> bool:
        if not self._confirmed and self._onCancel is not None:
            self._onCancel()
        return False


def OpenLaunchGui(
    reply: Reply,
    options: list[LaunchItem],
    teams: list[TeamItem] | None = None,
    currentTeam: int | None = None,
    config=None,
) -> LaunchGUI:
    """Show the LaunchGUI and map its outcome onto the WM_COPYDATA catalog:
    a pick replies `launch_selected {mode, team}`, a dismissal replies
    `cancelled {}`. The team preset is carried in the reply (not a separate
    team-change message) so AHK persists whatever preset was active at pick
    time; `team` is omitted when the launcher has no team dropdown."""

    selectedTeam = currentTeam

    def OnSelect(mode: int) -> None:
        data: dict = {"mode": mode}
        if selectedTeam is not None:
            data["team"] = selectedTeam
        reply("launch_selected", data)

    def OnTeamChange(teamID: int) -> None:
        nonlocal selectedTeam
        selectedTeam = teamID

    def OnCancel() -> None:
        reply("cancelled", {})

    window = LaunchGUI(
        options,
        teams,
        currentTeam,
        onSelect=OnSelect,
        onTeamChange=OnTeamChange,
        onCancel=OnCancel,
        config=config,
    )
    window.ShowCentered()
    return window
