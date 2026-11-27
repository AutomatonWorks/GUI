from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QComboBox, QDoubleSpinBox, QSpinBox, QWidget

# an open dropdown list is a separate view, so the wheel still scrolls through its options
WHEEL_PICKERS = (QSpinBox, QDoubleSpinBox, QComboBox)


class WheelGuard(QObject):
    """The mouse wheel never changes a number picker or a dropdown: scrolling a form past one would
    edit it by accident. The wheel scrolls the area holding the picker instead, so the form keeps scrolling."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (event.type() != QEvent.Type.Wheel) or not isinstance(watched, WHEEL_PICKERS):
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


def InstallWheelGuard(app: QApplication) -> None:
    guard = WheelGuard(app)
    app.installEventFilter(guard)
