from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtWidgets import QAbstractScrollArea, QLabel, QStackedWidget, QWidget

# ---- look (edit these to restyle every validation message) ----
ERROR_COLOR = "#C42B1C"
BUBBLE_STYLE = f"background: {ERROR_COLOR}; color: #FFFFFF; border-radius: 4px; padding: 3px 7px;"
BUBBLE_GAP = 2
REPOSITION_EVENTS = (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show)


class ErrorBubble(QLabel):
    """A validation message floating just under its field, over whatever is below it: it never pushes
    the rest of the form. It lives in the field's scroll content or tab page, so it scrolls and hides
    along with the field; it flips above the field when there is no room below."""

    def __init__(self, anchor: QWidget) -> None:
        super().__init__()
        self._anchor = anchor
        self._watched: list[QWidget] = []
        self.setStyleSheet(BUBBLE_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()
        anchor.destroyed.connect(self.deleteLater)

    def ShowMessage(self, message: str) -> None:
        if not message:
            self.hide()
            return
        self.setText(message)
        self._Attach()
        self.adjustSize()
        self._Place()
        self.show()
        self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self.isHidden():
            return False
        if (watched is self._anchor) and (event.type() == QEvent.Type.Hide) and self._anchor.isHidden():
            self.hide()
        elif event.type() in REPOSITION_EVENTS:
            self._Place()
        return False

    # parented late: the field is only in its final place once the form is built
    def _Attach(self) -> None:
        host = _Host(self._anchor)
        if self.parentWidget() is host:
            return
        for widget in self._watched:
            widget.removeEventFilter(self)
        self.setParent(host)
        self._watched = []
        widget = self._anchor
        while (widget is not None) and (widget is not host):
            widget.installEventFilter(self)
            self._watched.append(widget)
            widget = widget.parentWidget()

    def _Place(self) -> None:
        host = self.parentWidget()
        below = self._anchor.mapTo(host, QPoint(0, self._anchor.height() + BUBBLE_GAP))
        y = below.y()
        if (host.height() > 0) and ((y + self.height()) > host.height()):
            y = self._anchor.mapTo(host, QPoint(0, 0)).y() - BUBBLE_GAP - self.height()
        x = min(below.x(), max(0, host.width() - self.width()))
        self.move(x, max(0, y))


def _Host(anchor: QWidget) -> QWidget:
    """The scroll content or tab page holding the field, else its window."""
    widget = anchor
    while widget.parentWidget() is not None:
        parent = widget.parentWidget()
        area = parent.parentWidget()
        if isinstance(parent, QStackedWidget):
            return widget
        if isinstance(area, QAbstractScrollArea) and (parent is area.viewport()):
            return widget
        widget = parent
    return widget
