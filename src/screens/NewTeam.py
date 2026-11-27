from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from automaton_gui.ipc import Reply
from automaton_gui import GUIConstants as gc
from automaton_gui.framework.ResultDialog import DIALOG_ROOT_MARGINS, ResultDialog
from automaton_gui.framework.Widgets import ApplyFont, MakeButton, Separator

# ---- layout constants (edit these to restyle this screen) ----
WIN_WIDTH = 600
ROOT_SPACING = 16
CARD_SPACING = 12
CARD_MARGINS = (16, 14, 16, 14)
HEADING_FONT_SIZE = 16
PORTRAIT_PX = 60  # the QHD portrait crops' own size, so they stay sharp
PORTRAIT_RADIUS = 12
PORTRAIT_SPACING = 18
FIELD_GRID_SPACING = 10
SPIN_WIDTH = 90

# NewTeamGUI: shown before the launch menu when the game added a team the active
# account has never been asked about. AHK sends each team's agents (name + portrait
# path, in squad order) and the fields to fill; the answers go back in one reply.
#
# Python stays dumb: which teams are new, the ranges, and where answers are stored
# are all decided AHK-side. Closing the window answers nothing, so AHK asks again
# on the next launch.


@dataclass
class TeamAgent:
    name: str
    image: str = ""


@dataclass
class NewTeam:
    id: int
    label: str
    agents: list[TeamAgent] = field(default_factory=list)
    presetMax: int = 20
    presetValue: int = 1
    mindscapeLabel: str = ""  # "" -> the team has no mindscape setting
    mindscapeValue: int = 0


@dataclass
class TeamAnswer:
    id: int
    use: bool
    preset: int
    mindscape: int | None

    def AsDict(self) -> dict:
        return {"id": self.id, "use": 1 if self.use else 0, "preset": self.preset, "mindscape": self.mindscape}


def ParseNewTeams(raw: list) -> list[NewTeam]:
    teams = []
    for t in raw or []:
        mindscape = t.get("mindscape") or {}
        teams.append(NewTeam(
            id=int(t["id"]),
            label=str(t.get("label", "")),
            agents=[TeamAgent(str(a.get("name", "")), str(a.get("image", ""))) for a in t.get("agents", [])],
            presetMax=int(t.get("preset_max", 20)),
            presetValue=int(t.get("preset", 1) or 1),
            mindscapeLabel=str(mindscape.get("label", "")),
            mindscapeValue=int(mindscape.get("value", 0) or 0),
        ))
    return teams


def RoundedPortrait(path: str, size: int, radius: int) -> QPixmap | None:
    source = QPixmap(path) if path else None
    if source is None or source.isNull():
        return None
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return out


class TeamCard(QFrame):
    """One team: its agents in squad order, a 'use it' switch and the fields it needs."""

    def __init__(self, team: NewTeam, t: Callable[..., str]) -> None:
        super().__init__()
        self.team = team
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*CARD_MARGINS)
        layout.setSpacing(CARD_SPACING)

        name = QLabel(team.label)
        ApplyFont(name, gc.FONT_LIST, bold=True)
        layout.addWidget(name)
        layout.addLayout(self._AgentsRow(t))

        order = QLabel(t("new_team.order_note", "Your squad preset needs these agents in this order."))
        order.setWordWrap(True)
        order.setProperty("subtle", True)
        layout.addWidget(order)
        layout.addWidget(Separator())

        self.use = QCheckBox(t("new_team.use", "Enable this team"))
        self.use.setToolTip(t("new_team.use_help", "Enabled teams show up in the launch menu's team picker."))
        self.use.setChecked(True)
        layout.addWidget(self.use)
        layout.addLayout(self._Fields(t))
        self.use.toggled.connect(self._SyncEnabled)

    def _AgentsRow(self, t: Callable[..., str]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(PORTRAIT_SPACING)
        row.addStretch(1)
        for index, agent in enumerate(self.team.agents, start=1):
            col = QVBoxLayout()
            col.setSpacing(4)
            portrait = RoundedPortrait(agent.image, PORTRAIT_PX, PORTRAIT_RADIUS)
            if portrait is not None:
                art = QLabel()
                art.setPixmap(portrait)
                art.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                col.addWidget(art)
            agentName = QLabel(agent.name)
            agentName.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            ApplyFont(agentName, gc.APP_FONT_POINT_SIZE, bold=True)
            col.addWidget(agentName)
            slot = QLabel(t("new_team.slot", "Slot {n}", n=index))
            slot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            slot.setProperty("subtle", True)
            col.addWidget(slot)
            row.addLayout(col)
        row.addStretch(1)
        return row

    def _Fields(self, t: Callable[..., str]) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(FIELD_GRID_SPACING)
        grid.setVerticalSpacing(FIELD_GRID_SPACING)
        self.presetLabel = QLabel(t("new_team.preset", "Squad preset position"))
        self.preset = self._Spin(1, self.team.presetMax, self.team.presetValue)
        grid.addWidget(self.presetLabel, 0, 0)
        grid.addWidget(self.preset, 0, 1)
        self.mindscape: QSpinBox | None = None
        if self.team.mindscapeLabel:
            self.mindscapeLabel = QLabel(t("new_team.mindscape", "{name} mindscape", name=self.team.mindscapeLabel))
            self.mindscape = self._Spin(0, 6, self.team.mindscapeValue)
            grid.addWidget(self.mindscapeLabel, 1, 0)
            grid.addWidget(self.mindscape, 1, 1)
        grid.setColumnStretch(2, 1)
        return grid

    @staticmethod
    def _Spin(low: int, high: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(min(max(value, low), high))
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setFixedWidth(SPIN_WIDTH)
        return spin

    def _SyncEnabled(self, used: bool) -> None:
        for widget in (self.presetLabel, self.preset):
            widget.setEnabled(used)
        if self.mindscape is not None:
            self.mindscapeLabel.setEnabled(used)
            self.mindscape.setEnabled(used)

    def Answer(self) -> TeamAnswer:
        used = self.use.isChecked()
        return TeamAnswer(
            id=self.team.id,
            use=used,
            preset=self.preset.value() if used else 0,
            mindscape=self.mindscape.value() if self.mindscape is not None else None,
        )


class NewTeamGUI(ResultDialog):
    winWidth = WIN_WIDTH

    def __init__(
        self,
        teams: list[NewTeam],
        onResult: Callable[[list[TeamAnswer]], None],
        account: str = "",
        strings: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._teams = teams
        self._account = account
        self._onResult = onResult
        self._cards: list[TeamCard] = []
        self.title = (strings or {}).get("new_team.title", "New team available")
        super().__init__(parent, strings=strings)

    def Build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(*DIALOG_ROOT_MARGINS)
        root.setSpacing(ROOT_SPACING)

        heading = QLabel(self.T("new_team.heading", "A new team is available!"))
        ApplyFont(heading, HEADING_FONT_SIZE, bold=True)
        root.addWidget(heading)
        intro = QLabel(self.T("new_team.intro", "Do you want to enable it on {account}? You can change this later in Account settings.",
                              account=self._account))
        intro.setWordWrap(True)
        intro.setProperty("subtle", True)
        root.addWidget(intro)

        for team in self._teams:
            card = TeamCard(team, self.T)
            self._cards.append(card)
            root.addWidget(card)

        buttons = QHBoxLayout()
        buttons.setSpacing(gc.SPACING_ROW)
        buttons.addStretch(1)
        later = MakeButton(self.T("new_team.later", "Ask me later"))
        later.clicked.connect(self.close)
        buttons.addWidget(later)
        save = MakeButton(self.T("new_team.save", "Save"), primary=True)
        save.clicked.connect(self._Accept)
        buttons.addWidget(save)
        root.addLayout(buttons)
        self.setCentralWidget(central)

    def OnEnter(self) -> None:
        self._Accept()

    def Answers(self) -> list[TeamAnswer]:
        return [card.Answer() for card in self._cards]

    def _Accept(self) -> None:
        answers = self.Answers()
        self._ResolveWith(lambda: self._onResult(answers))

    # Closing without saving answers nothing; AHK asks again next launch.
    def _ReportDismissal(self) -> None:
        self._onResult([])


def OpenNewTeamGui(
    reply: Reply,
    teams: list[NewTeam],
    account: str = "",
    strings: dict | None = None,
) -> NewTeamGUI:
    """Show the NewTeamGUI and reply `new_team_result {teams: [{id, use, preset, mindscape}]}`;
    an empty list when the window is closed without saving."""

    def OnResult(answers: list[TeamAnswer]) -> None:
        reply("new_team_result", {"teams": [a.AsDict() for a in answers]})

    window = NewTeamGUI(teams, OnResult, account=account, strings=strings)
    window.ShowCentered()
    return window
