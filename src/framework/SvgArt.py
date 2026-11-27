from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from automaton_gui.theme.Palettes import HexOf
from automaton_gui.theme.Theme import theme

# One-colour SVG art (the game logos) drawn for the active theme: the SVG paints its
# ink #ffffff and its cut-outs #000000; the ink becomes black on a light theme and
# white on a dark one, the cut-outs the window background.

SVG_INK = "#ffffff"
SVG_CUTOUT = "#000000"
INK_LIGHT = "#000000"
INK_DARK = "#FFFFFF"


def IsSvg(path: str) -> bool:
    return path.lower().endswith(".svg")


def ThemedSvgPixmap(path: str, width: int, height: int) -> QPixmap | None:
    """The art scaled to fit width x height (aspect kept), or None when it cannot be read."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    ink = INK_DARK if theme.isDark else INK_LIGHT
    # through neutral markers: the light ink is the cut-out token and the cut-out may be the ink token
    text = text.replace(SVG_INK, "@ink@").replace(SVG_CUTOUT, "@cutout@")
    text = text.replace("@ink@", ink).replace("@cutout@", HexOf(theme.palette.bg))
    renderer = QSvgRenderer(QByteArray(text.encode("utf-8")))
    if not renderer.isValid():
        return None
    size = renderer.defaultSize().scaled(QSize(width, height), Qt.AspectRatioMode.KeepAspectRatio)
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()
    return pixmap
