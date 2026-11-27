from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy

# A right-aligned value that wraps at its spaces instead of widening its column, and
# scrolls sideways only when a single word is still wider than the room it has.


class WrappingValue(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setWidget(self.label)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")

    def setText(self, text: str) -> None:
        self.label.setText(text)
        # wrapping only breaks at plain spaces, so the longest word is as narrow as the text gets
        metrics = self.label.fontMetrics()
        self.label.setMinimumWidth(max((metrics.horizontalAdvance(word) for word in text.split(" ")), default=0))
        self._FitHeight()

    def Text(self) -> str:
        return self.label.text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._FitHeight()

    # As tall as the wrapped text, plus the scroll bar when the longest word still overflows;
    # scrolling text reads from the left, where the bar starts.
    def _FitHeight(self) -> None:
        width = self.viewport().width()
        narrowest = self.label.minimumWidth()
        overflows = width < narrowest
        self.label.setAlignment((Qt.AlignmentFlag.AlignLeft if overflows else Qt.AlignmentFlag.AlignRight)
                                | Qt.AlignmentFlag.AlignVCenter)
        height = self.label.heightForWidth(max(width, narrowest))
        if overflows:
            height += self.horizontalScrollBar().sizeHint().height()
        self.setFixedHeight(max(height, self.label.fontMetrics().height()))
