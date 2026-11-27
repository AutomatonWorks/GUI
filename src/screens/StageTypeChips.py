from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QButtonGroup, QPushButton, QStyle, QStyleOptionButton, QStylePainter, QWidget

from automaton_gui.framework.FlowLayout import FlowLayout
from automaton_gui.framework.Widgets import BADGE_GAP, BADGE_PAD_X, ApplyFont, PaintBadge
from automaton_gui.theme.Palettes import HexOf
from automaton_gui.theme.Theme import theme

# The stage picker's stage types as a row of chips that wraps when it runs out of width.
# One chip is always picked; Left/Right move the pick while the row has focus.

CHIP_FONT_SIZE = 10
CHIP_HEIGHT = 30
CHIP_PAD_X = 14
CHIP_SPACING = 6


class TypeChip(QPushButton):
    """A checkable chip with the type's name and, after it, its drop-bonus badge."""

    def __init__(self, name: str, typeID: int, badge: str) -> None:
        super().__init__(name)
        self.typeID = typeID
        self.badge = badge
        self.setCheckable(True)
        self.setProperty("chip", True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        ApplyFont(self, CHIP_FONT_SIZE)

    def _BadgeWidth(self) -> int:
        if not self.badge:
            return 0
        return BADGE_GAP + QFontMetrics(self.font()).horizontalAdvance(self.badge) + 2 * BADGE_PAD_X

    def sizeHint(self) -> QSize:
        text = QFontMetrics(self.font()).horizontalAdvance(self.text())
        return QSize(text + self._BadgeWidth() + 2 * CHIP_PAD_X, CHIP_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        pal = theme.palette
        color = QColor(HexOf(pal.primaryFg if self.isChecked() else pal.text))
        metrics = QFontMetrics(self.font())
        textWidth = metrics.horizontalAdvance(self.text())
        left = (self.width() - textWidth - self._BadgeWidth()) / 2
        painter.setPen(color)
        painter.drawText(QRectF(left, 0, textWidth + 1, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.badge:
            PaintBadge(painter, left + textWidth + BADGE_GAP, self.height() / 2, self.badge, color, self.font())


class TypeChips(QWidget):
    """The chip row. Emits `changed(typeID)` when the pick moves."""

    changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._layout = FlowLayout(self, CHIP_SPACING)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._chips: list[TypeChip] = []
        self._group.idToggled.connect(self._OnToggled)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def AddChip(self, name: str, typeID: int, badge: str = "") -> None:
        chip = TypeChip(name, typeID, badge)
        self._group.addButton(chip, len(self._chips))
        self._chips.append(chip)
        self._layout.addWidget(chip)

    def count(self) -> int:
        return len(self._chips)

    def SingleRowWidth(self) -> int:
        """The width the whole row needs to fit on one line."""
        chips = sum(chip.sizeHint().width() for chip in self._chips)
        gaps = CHIP_SPACING * max(0, len(self._chips) - 1)
        margins = self._layout.contentsMargins()
        return chips + gaps + margins.left() + margins.right()

    def Chip(self, index: int) -> TypeChip:
        return self._chips[index]

    def CurrentIndex(self) -> int:
        return self._group.checkedId()

    def CurrentId(self) -> int:
        index = self.CurrentIndex()
        return self._chips[index].typeID if index >= 0 else 0

    def SelectIndex(self, index: int) -> None:
        if 0 <= index < len(self._chips):
            self._chips[index].setChecked(True)

    def SelectId(self, typeID: int) -> bool:
        index = next((i for i, chip in enumerate(self._chips) if chip.typeID == typeID), -1)
        self.SelectIndex(index)
        return index >= 0

    def _OnToggled(self, index: int, checked: bool) -> None:
        if checked:
            if self.hasFocus():
                self._MarkFocus(True)
            self.changed.emit(self._chips[index].typeID)

    def keyPressEvent(self, event) -> None:
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step is None or not self._chips:
            super().keyPressEvent(event)
            return
        self.SelectIndex((self.CurrentIndex() + step) % len(self._chips))

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._MarkFocus(True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._MarkFocus(False)

    def _MarkFocus(self, focused: bool) -> None:
        for chip in self._chips:
            chip.setProperty("focused", focused and chip.isChecked())
            chip.style().unpolish(chip)
            chip.style().polish(chip)
