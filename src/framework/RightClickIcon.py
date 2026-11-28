from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# Drawn large and scaled down by the line edit: a mouse outline with its right button filled
ICON_SIZE = 64
BODY = QRectF(14, 4, 36, 56)
BODY_RADIUS = 16
BUTTON_SPLIT_Y = 30
PEN_WIDTH = 5


def RightClickIcon(color: QColor) -> QIcon:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    centerX = BODY.center().x()
    body = QPainterPath()
    body.addRoundedRect(BODY, BODY_RADIUS, BODY_RADIUS)
    rightButton = QPainterPath()
    rightButton.addRect(QRectF(centerX, BODY.top(), (BODY.width() / 2), (BUTTON_SPLIT_Y - BODY.top())))
    painter.fillPath(body.intersected(rightButton), color)
    painter.setPen(QPen(color, PEN_WIDTH))
    painter.drawPath(body)
    painter.drawLine(QPointF(centerX, BODY.top()), QPointF(centerX, BUTTON_SPLIT_Y))
    painter.drawLine(QPointF(BODY.left(), BUTTON_SPLIT_Y), QPointF(BODY.right(), BUTTON_SPLIT_Y))
    painter.end()
    return QIcon(pixmap)
