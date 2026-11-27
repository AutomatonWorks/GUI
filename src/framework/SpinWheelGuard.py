from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QDoubleSpinBox, QSpinBox, QWidget

NUMBER_PICKERS = (QSpinBox, QDoubleSpinBox)


class SpinWheelGuard(QObject):
    """The mouse wheel never changes a number picker: scrolling a form past one would edit it by
    accident. The wheel scrolls the area holding the picker instead, so the form keeps scrolling."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (event.type() != QEvent.Type.Wheel) or not isinstance(watched, NUMBER_PICKERS):
            return False
        area = _ScrollAreaOf(watched)
        if area is not None:
            QCoreApplication.sendEvent(area.verticalScrollBar(), event)
        return True


def _ScrollAreaOf(widget: QWidget) -> QAbstractScrollArea | None:
    holder = widget.parentWidget()
    while (holder is not None) and not isinstance(holder, QAbstractScrollArea):
        holder = holder.parentWidget()
    return holder


def InstallSpinWheelGuard(app: QApplication) -> None:
    guard = SpinWheelGuard(app)
    app.installEventFilter(guard)
