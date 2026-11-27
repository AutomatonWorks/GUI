from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import ApplyFont, Separator
from automaton_gui.screens.NewTeam import PORTRAIT_PX, PORTRAIT_RADIUS, PORTRAIT_SPACING, RoundedPortrait
from automaton_gui.screens.StageTeam import TeamOption

# One team in the Team settings window: portraits in squad order, its Enable box
# and the team's slot and mindscape. Reading and writing the account is the window's job.

CARD_MARGINS = (16, 14, 16, 14)
CARD_SPACING = 10
FIELD_GRID_SPACING = 10
SPIN_WIDTH = 90
SLOT_MIN = 1
SLOT_MAX = 20  # NewTeamPrompt.PRESET_MAX
MINDSCAPE_MIN = 0
MINDSCAPE_MAX = 6
MUTED_PORTRAIT_OPACITY = 0.35


def MutedPortrait(portrait: QPixmap) -> QPixmap:
    """`portrait` in grayscale and faded, keeping its rounded transparent corners."""
    gray = portrait.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    gray = gray.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    mask = QPainter(gray)
    mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    mask.drawPixmap(0, 0, portrait)
    mask.end()
    out = QPixmap(portrait.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setOpacity(MUTED_PORTRAIT_OPACITY)
    painter.drawImage(0, 0, gray)
    painter.end()
    return out


class TeamSettingsCard(QFrame):
    def __init__(self, team: TeamOption, t: Callable[..., str]) -> None:
        super().__init__()
        self.team = team
        self._portraits: list[tuple[QLabel, QPixmap, QPixmap]] = []
        self._shownMindscape: int | None = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*CARD_MARGINS)
        layout.setSpacing(CARD_SPACING)

        self._portraitRow = QHBoxLayout()
        self._portraitRow.setSpacing(PORTRAIT_SPACING)
        layout.addLayout(self._portraitRow)
        self.name = QLabel()
        self.name.setWordWrap(True)
        ApplyFont(self.name, gc.FONT_LIST, bold=True)
        layout.addWidget(self.name)
        layout.addWidget(Separator())

        self.have = QCheckBox(t("team_settings.have", "Enable"))
        layout.addWidget(self.have)
        layout.addLayout(self._Fields(t))
        layout.addStretch(1)
        self.have.toggled.connect(self._SyncEnabled)
        if self.mindscape is not None:
            self.mindscape.valueChanged.connect(self.ShowMindscape)
        self.ShowMindscape(MINDSCAPE_MIN)
        self._SyncEnabled(False)

    # The label and portraits follow the mindscape: some teams change their squad order with it
    def ShowMindscape(self, mindscape: int) -> None:
        if mindscape == self._shownMindscape:
            return
        self._shownMindscape = mindscape
        label, images = self.team.AtMindscape(mindscape)
        self.name.setText(label)
        self._FillPortraits(images)
        self._SyncEnabled(self.have.isChecked())

    def Label(self) -> str:
        return self.name.text()

    def _FillPortraits(self, images: tuple[str, ...]) -> None:
        row = self._portraitRow
        while row.count():
            widget = row.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        self._portraits = []
        row.addStretch(1)
        for image in images:
            portrait = RoundedPortrait(image, PORTRAIT_PX, PORTRAIT_RADIUS)
            if portrait is None:
                continue
            art = QLabel()
            art.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self._portraits.append((art, portrait, MutedPortrait(portrait)))
            row.addWidget(art)
        row.addStretch(1)

    def _Fields(self, t: Callable[..., str]) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(FIELD_GRID_SPACING)
        grid.setVerticalSpacing(FIELD_GRID_SPACING)
        self.slotLabel = QLabel(t("team_settings.slot", "Squad preset slot"))
        self.slot = self._Spin(SLOT_MIN, SLOT_MAX)
        grid.addWidget(self.slotLabel, 0, 0)
        grid.addWidget(self.slot, 0, 1)
        self.mindscapeLabel: QLabel | None = None
        self.mindscape: QSpinBox | None = None
        if self.team.mindscapeKey:
            self.mindscapeLabel = QLabel(
                t("team_settings.mindscape", "{name} mindscape", name=self.team.mindscapeLabel))
            self.mindscape = self._Spin(MINDSCAPE_MIN, MINDSCAPE_MAX)
            grid.addWidget(self.mindscapeLabel, 1, 0)
            grid.addWidget(self.mindscape, 1, 1)
        grid.setColumnStretch(2, 1)
        return grid

    @staticmethod
    def _Spin(low: int, high: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setFixedWidth(SPIN_WIDTH)
        return spin

    def _SyncEnabled(self, have: bool) -> None:
        for widget in (self.name, self.slotLabel, self.slot, self.mindscapeLabel, self.mindscape):
            if widget is not None:
                widget.setEnabled(have)
        for art, portrait, muted in self._portraits:
            art.setPixmap(portrait if have else muted)

    def Load(self, have: bool, slot: int, mindscape: int) -> None:
        self.have.setChecked(have)
        self._SyncEnabled(have)
        self.slot.setValue(max(slot, SLOT_MIN))
        if self.mindscape is not None:
            self.mindscape.setValue(mindscape)

    def IsChecked(self) -> bool:
        return self.have.isChecked()

    def State(self) -> tuple[bool, int, int | None]:
        return self.IsChecked(), self.slot.value(), (None if self.mindscape is None else self.mindscape.value())
