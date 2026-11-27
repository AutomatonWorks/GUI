from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)

from automaton_gui.framework.SvgArt import IsSvg, ThemedSvgPixmap
from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.screens.NewTeam import RoundedPortrait
from automaton_gui.screens.StageTeam import TeamOption

# The stage picker's team block: a small caps caption, a dropdown with the team's name
# centred, and the picked team's portraits under it. The open list shows each team as
# its portraits plus its name, left aligned, a few rows at a time.

POPUP_PORTRAIT_PX = 40
POPUP_PORTRAIT_RADIUS = 8
POPUP_PORTRAIT_GAP = 6
POPUP_ROW_PADDING = 6
POPUP_TEXT_GAP = 12
POPUP_VISIBLE_ROWS = 4
COMBO_MIN_HEIGHT = 34
PORTRAIT_GAP = 14
BLOCK_SPACING = 6
PORTRAITS_TOP_GAP = 6
CAPTION_FONT_SIZE = 9
PORTRAITS_ROLE = Qt.ItemDataRole.UserRole + 1


def CaptionLabel(text: str) -> QLabel:
    """The small upper-case caption over a field (TEAM, BATTERY)."""
    label = QLabel(text)
    label.setProperty("subtle", True)
    ApplyFont(label, CAPTION_FONT_SIZE, bold=True)
    font = QFont(label.font())
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
    label.setFont(font)
    return label


class TeamRowDelegate(QStyledItemDelegate):
    """An open-list row: the team's portraits, then its name."""

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width(), POPUP_PORTRAIT_PX + 2 * POPUP_ROW_PADDING)

    def paint(self, painter, option, index) -> None:
        style = option.widget.style() if option.widget else None
        if style is not None:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        x = option.rect.left() + POPUP_ROW_PADDING
        top = option.rect.top() + (option.rect.height() - POPUP_PORTRAIT_PX) // 2
        for pixmap in index.data(PORTRAITS_ROLE) or []:
            painter.drawPixmap(x, top, pixmap)
            x += POPUP_PORTRAIT_PX + POPUP_PORTRAIT_GAP
        textRect = QRect(x + POPUP_TEXT_GAP - POPUP_PORTRAIT_GAP, option.rect.top(),
                          option.rect.right() - x, option.rect.height())
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        role = option.palette.ColorRole.HighlightedText if selected else option.palette.ColorRole.Text
        painter.save()
        painter.setFont(option.font)
        painter.setPen(option.palette.color(role))
        painter.drawText(textRect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         index.data(Qt.ItemDataRole.DisplayRole))
        painter.restore()


class CenteredCombo(QComboBox):
    """A dropdown whose closed box shows the current text centred; the list opens below it."""

    def __init__(self) -> None:
        super().__init__()
        # combobox-popup: 0 opens the list below the box; the list keeps the box's font
        # (Qt would give it the smaller menu font)
        self.setStyleSheet(
            "QComboBox { combobox-popup: 0; }"
            f" QAbstractItemView {{ font-size: {self.font().pointSize()}pt; }}")
        self.setMaxVisibleItems(POPUP_VISIBLE_ROWS)
        self.setMinimumHeight(COMBO_MIN_HEIGHT)
        self.setItemDelegate(TeamRowDelegate(self))

    def paintEvent(self, _event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        text = option.currentText
        option.currentText = ""
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        field = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxEditField, self)
        arrow = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, self)
        # centred on the whole box, not just the text field, so it lines up with the portraits
        rect = QRect(field.left() + arrow.width(), field.top(), field.width() - arrow.width(), field.height())
        elided = self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided)


class TeamPicker(QWidget):
    """Caption, team dropdown and the picked team's portraits."""

    teamChanged = Signal(int)

    def __init__(self, teams: list[TeamOption], caption: str, portraitPx: int, placeholder: str = "") -> None:
        super().__init__()
        self._teams = list(teams)
        self._portraitPx = portraitPx
        self._placeholder = placeholder
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(BLOCK_SPACING)
        layout.addWidget(CaptionLabel(caption))

        self._combo = CenteredCombo()
        for team in self._teams:
            self._combo.addItem(team.label, team.id)
            self._combo.setItemData(self._combo.count() - 1, self._Portraits(team, POPUP_PORTRAIT_PX,
                                                                            POPUP_PORTRAIT_RADIUS), PORTRAITS_ROLE)
        self._combo.currentIndexChanged.connect(self._OnChanged)
        layout.addWidget(self._combo)

        self._portraitRow = QHBoxLayout()
        self._portraitRow.setSpacing(PORTRAIT_GAP)
        self._portraitRow.setContentsMargins(0, PORTRAITS_TOP_GAP, 0, 0)
        layout.addLayout(self._portraitRow)
        self._ShowPortraits()

    @property
    def combo(self) -> QComboBox:
        return self._combo

    def TeamId(self) -> int:
        return int(self._combo.currentData() or 0)

    def SetTeam(self, teamID: int) -> None:
        index = self._combo.findData(teamID)
        if index < 0:
            return
        if index == self._combo.currentIndex():
            self._ShowPortraits()  # same team, but the row may be showing the placeholder
        else:
            self._combo.setCurrentIndex(index)

    def _OnChanged(self, _index: int) -> None:
        self._ShowPortraits()
        self.teamChanged.emit(self.TeamId())

    def _ShowPortraits(self) -> None:
        team = next((t for t in self._teams if t.id == self.TeamId()), None)
        radius = max(POPUP_PORTRAIT_RADIUS, self._portraitPx // 5)
        self._FillPortraitRow(self._Portraits(team, self._portraitPx, radius) if team else [])

    # Nothing picked yet: the game's logo where the portraits go, as wide as three of them,
    # under an empty dropdown so it never sits next to a team.
    def ShowPlaceholder(self) -> None:
        width = (3 * self._portraitPx) + (2 * PORTRAIT_GAP)
        art = ThemedSvgPixmap(self._placeholder, width, self._portraitPx) if IsSvg(self._placeholder) else None
        if art is None:
            self._ShowPortraits()
            return
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(-1)
        self._combo.blockSignals(False)
        self._FillPortraitRow([art], fixed=False)

    def _FillPortraitRow(self, pixmaps: list[QPixmap], fixed: bool = True) -> None:
        while self._portraitRow.count():
            item = self._portraitRow.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self._portraitRow.addStretch(1)
        for pixmap in pixmaps:
            art = QLabel()
            art.setPixmap(pixmap)
            art.setAlignment(Qt.AlignmentFlag.AlignCenter)
            art.setFixedHeight(self._portraitPx)
            if fixed:
                art.setFixedWidth(self._portraitPx)
            self._portraitRow.addWidget(art)
        self._portraitRow.addStretch(1)

    @staticmethod
    def _Portraits(team: TeamOption, size: int, radius: int) -> list[QPixmap]:
        pixmaps = (RoundedPortrait(path, size, radius) for path in team.images)
        return [pixmap for pixmap in pixmaps if pixmap is not None]
