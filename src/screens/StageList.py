from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import BADGE_GAP, ApplyFont, PaintBadge
from automaton_gui.theme.Palettes import HexOf, Mix
from automaton_gui.theme.Theme import theme

# The stage picker's type and stage lists: rows with an optional drop-bonus pill, and
# non-selectable group headers the keys and the mouse step over.

LIST_FONT_SIZE = gc.FONT_LIST
# Row height (px) the list QSS pins each item to, and how many rows the box
# caps at unless the caller asks for another count: whole rows only, no
# half-row dangling. The list is height-capped to ROWS * ROW_H + frame
# (a free-stretching list shows a partial last row).
LIST_ROW_HEIGHT = 28
LIST_VISIBLE_ROWS = 11
GROUP_HEADER_TINT = 0.18  # how far the header band leans from the list surface toward the accent
GROUP_HEADER_FONT_SIZE = gc.FONT_LIST - 1
BADGE_ROLE = Qt.ItemDataRole.UserRole + 1


class BadgeDelegate(QStyledItemDelegate):
    """Paints the BADGE_ROLE pill after the item text, and the group header bands, in the active palette."""

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        if not index.flags() & Qt.ItemFlag.ItemIsSelectable:
            option.state &= ~QStyle.StateFlag.State_MouseOver
            pal = theme.palette
            option.backgroundBrush = QBrush(QColor(HexOf(Mix(pal.surface, pal.accent, GROUP_HEADER_TINT))))
            option.palette.setColor(QPalette.ColorRole.Text, QColor(HexOf(pal.text)))

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        badge = index.data(BADGE_ROLE)
        if not badge:
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        textRect = opt.widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)
        left = textRect.left() + opt.fontMetrics.horizontalAdvance(opt.text) + BADGE_GAP
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        PaintBadge(painter, left, textRect.center().y(), badge,
                    QColor(HexOf(theme.palette.primaryFg if selected else theme.palette.accent)))


class GroupedList(QListWidget):
    """Rows that cannot be selected (the group headers) take no part in keys or the mouse: arrows
    step over them, and a press, drag, release or double-click on one is swallowed whole."""

    def __init__(self, visibleRows: int = LIST_VISIBLE_ROWS) -> None:
        super().__init__()
        self._headerGesture = False
        ApplyFont(self, LIST_FONT_SIZE)
        self.setStyleSheet(f"QListWidget::item {{ height: {LIST_ROW_HEIGHT}px; padding: 0px 4px; }}")
        self.setMaximumHeight(LIST_ROW_HEIGHT * visibleRows + 2)
        self.setItemDelegate(BadgeDelegate(self))

    def AddRow(self, text: str, itemId: int, badge: str) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, itemId)
        item.setData(BADGE_ROLE, badge)
        self.addItem(item)

    def AddGroupHeader(self, text: str) -> None:
        header = QListWidgetItem(text)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont(self.font())
        font.setPointSize(GROUP_HEADER_FONT_SIZE)
        font.setBold(True)
        header.setFont(font)
        self.addItem(header)

    def _OverHeader(self, event) -> bool:
        item = self.itemAt(event.position().toPoint())
        return item is not None and not item.flags() & Qt.ItemFlag.ItemIsSelectable

    def mousePressEvent(self, event) -> None:
        self._headerGesture = self._OverHeader(event)
        if self._headerGesture:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self._headerGesture = self._OverHeader(event)
        if self._headerGesture:
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._headerGesture or self._OverHeader(event):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._headerGesture:
            self._headerGesture = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    _STEP = {
        QAbstractItemView.CursorAction.MoveUp: -1,
        QAbstractItemView.CursorAction.MovePageUp: -1,
        QAbstractItemView.CursorAction.MoveEnd: -1,
        QAbstractItemView.CursorAction.MoveDown: 1,
        QAbstractItemView.CursorAction.MovePageDown: 1,
        QAbstractItemView.CursorAction.MoveHome: 1,
    }

    def moveCursor(self, cursorAction, modifiers):
        index = super().moveCursor(cursorAction, modifiers)
        step = self._STEP.get(cursorAction)
        if step is None or not index.isValid():
            return index
        row = index.row()
        while 0 <= row < self.count() and not self.item(row).flags() & Qt.ItemFlag.ItemIsSelectable:
            row += step
        if 0 <= row < self.count():
            return self.model().index(row, 0)
        return self.currentIndex()
