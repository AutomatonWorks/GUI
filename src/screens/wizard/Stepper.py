from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from automaton_gui.theme.Palettes import HexOf
from automaton_gui.theme.Theme import theme

# ---- layout constants (edit these to restyle the stepper) ----
MARGINS = (16, 11, 16, 11)
SPACING = 6
DOT_SIZE = 20
LINE_SIZE = (18, 2)
DOT_BORDER = 2


class Stepper(QWidget):
    """The numbered steps across the top of the setup wizard: done ones filled, the current one ringed."""

    def __init__(self, titles: list[str]) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(*MARGINS)
        row.setSpacing(SPACING)
        self._dots: list[QLabel] = []
        self._names: list[QLabel] = []
        self._lines: list[QFrame] = []
        for index, title in enumerate(titles):
            if index > 0:
                line = QFrame()
                line.setFixedSize(*LINE_SIZE)
                self._lines.append(line)
                row.addWidget(line)
            dot = QLabel(str(index + 1))
            dot.setFixedSize(DOT_SIZE, DOT_SIZE)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name = QLabel(title)
            self._dots.append(dot)
            self._names.append(name)
            row.addWidget(dot)
            row.addWidget(name)
        row.addStretch(1)

    def SetCurrent(self, current: int) -> None:
        palette = theme.palette
        accent, subtle, text = HexOf(palette.accent), HexOf(palette.subtle), HexOf(palette.text)
        for index, (dot, name) in enumerate(zip(self._dots, self._names)):
            radius = f"border-radius: {DOT_SIZE // 2}px; font-size: 10px; font-weight: 600;"
            if index < current:
                dot.setStyleSheet(f"{radius} background: {accent}; border: {DOT_BORDER}px solid {accent}; color: white;")
            elif index == current:
                dot.setStyleSheet(f"{radius} border: {DOT_BORDER}px solid {accent}; color: {accent};")
            else:
                dot.setStyleSheet(f"{radius} border: {DOT_BORDER}px solid {subtle}; color: {subtle};")
            weight = "600" if (index == current) else "400"
            name.setStyleSheet(f"color: {text if (index <= current) else subtle}; font-weight: {weight};")
        for index, line in enumerate(self._lines):
            line.setStyleSheet(f"background: {accent if (index < current) else subtle};")
