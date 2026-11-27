from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automaton_gui import GUIConstants as gc

BADGE_FONT_SIZE = 9
BADGE_PAD_X = 6
BADGE_PAD_X_RATIO = 0.45
BADGE_PAD_Y = 1
BADGE_GAP = 8


def ElideText(widget: QWidget, text: str, width: int) -> str:
    """Truncate `text` with an ellipsis so it fits `width` px in `widget`'s own
    font - shared by any label/button that shows user-authored text (an
    account name, a stage name, ...) next to a fixed-width control, so a long
    pick elides instead of forcing the control - or the window - wider."""
    return QFontMetrics(widget.font()).elidedText(text, Qt.TextElideMode.ElideRight, width)


def Separator() -> QFrame:
    """A thin horizontal divider: a crisp hairline that softly fades below it.
    Shared by the screens (launch, macro, ...) so every divider looks the same."""
    line = QFrame()
    line.setObjectName("card")
    line.setFixedHeight(3)
    line.setStyleSheet(
        "#card { border: none; background-color: "
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #CECECE, stop:1 rgba(43,43,43,0)); }"
    )
    return line


def ApplyFont(widget: QWidget, size: int | None = None, *, bold: bool = False,
               italic: bool = False) -> None:
    """Set point size / bold / italic on a widget's font in one call, replacing the
    font()/setPointSize()/setFont() dance repeated across every screen."""
    font = widget.font()
    if size is not None:
        font.setPointSize(size)
    font.setBold(bold)
    font.setItalic(italic)
    widget.setFont(font)


def PaintBadge(painter: QPainter, left: float, centerY: float, text: str, color: QColor,
                font: QFont | None = None) -> None:
    """The outlined x2/x3 pill. Given the neighbouring text's `font`, it shares
    that text's size and baseline; without one it is a small bold tag."""
    painter.save()
    if font is None:
        font = painter.font()
        font.setPointSize(BADGE_FONT_SIZE)
        font.setBold(True)
    painter.setFont(font)
    metrics = QFontMetrics(font)
    height = metrics.height() + 2 * BADGE_PAD_Y
    # the round ends swallow a fixed padding at larger sizes
    padX = max(BADGE_PAD_X, height * BADGE_PAD_X_RATIO)
    rect = QRectF(left, centerY - height / 2, metrics.horizontalAdvance(text) + 2 * padX, height)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, 1.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect, height / 2, height / 2)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


def TrimTransparent(pixmap: QPixmap, threshold: int = 8) -> QPixmap:
    """Crop a pixmap to the box that actually has pixels in it.

    The stage artwork is transparent PNGs with generous padding, so scaling one
    to fit a slot mostly scales empty space and the art ends up tiny. Cropping to
    the opaque bounds first means the slot is filled by the thing you want to see.

    Rows are read a scanline at a time and tested with max() over the alpha bytes,
    so the common all-empty rows cost one C-level pass instead of a Python loop
    per pixel. A fully transparent image is returned untouched.
    """
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    top, bottom, left, right = height, -1, width, -1
    for y in range(height):
        alphas = bytes(image.constScanLine(y))[:width * 4][3::4]
        if not alphas or max(alphas) <= threshold:
            continue
        rowLeft = next(i for i, a in enumerate(alphas) if a > threshold)
        rowRight = width - 1 - next(i for i, a in enumerate(reversed(alphas)) if a > threshold)
        top = min(top, y)
        bottom = y
        left = min(left, rowLeft)
        right = max(right, rowRight)
    if bottom < 0:
        return pixmap
    return pixmap.copy(left, top, right - left + 1, bottom - top + 1)

# Spacing between stacked sprites, as a share of the tallest piece.
GAP_RATIO = 0.18
GAP_MIN_PX = 6


def _AlphaColumns(image: QImage, threshold: int) -> list[bool]:
    """Which columns contain anything, so sprites can be split on the empty ones."""
    width, height = image.width(), image.height()
    filled = [False] * width
    for y in range(height):
        alphas = bytes(image.constScanLine(y))[:width * 4][3::4]
        if not alphas or max(alphas) <= threshold:
            continue   # an empty row costs one C-level pass, not width iterations
        for x, alpha in enumerate(alphas):
            if alpha > threshold:
                filled[x] = True
    return filled


def StackSprites(pixmap: QPixmap, threshold: int = 8, gap: int | None = None) -> QPixmap:
    """Split a sprite sheet on its empty columns and restack the pieces vertically.

    Several stage images are two icons side by side on a wide transparent canvas.
    Fitting that into a tall, narrow slot wastes most of the height and leaves the
    icons tiny, so each piece is cropped and they are stacked instead - the same
    art, filling the space it is given.

    One piece (or none) just comes back trimmed, so this is safe on any image.

    The gap defaults to a fraction of the piece height rather than a pixel count:
    it is inserted BEFORE the caller scales the result, so a fixed value would
    come out different for every source resolution.
    """
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    filled = _AlphaColumns(image, threshold)

    spans: list[tuple[int, int]] = []
    start = None
    for x, hasContent in enumerate(filled):
        if hasContent and start is None:
            start = x
        elif not hasContent and start is not None:
            spans.append((start, x - 1))
            start = None
    if start is not None:
        spans.append((start, len(filled) - 1))

    if len(spans) < 2:
        return TrimTransparent(pixmap, threshold)

    pieces = [TrimTransparent(pixmap.copy(x0, 0, x1 - x0 + 1, pixmap.height()), threshold)
              for x0, x1 in spans]
    width = max(piece.width() for piece in pieces)
    if gap is None:
        tallest = max(piece.height() for piece in pieces)
        gap = max(GAP_MIN_PX, round(tallest * GAP_RATIO))
    height = sum(piece.height() for piece in pieces) + gap * (len(pieces) - 1)
    stacked = QPixmap(width, height)
    stacked.fill(Qt.GlobalColor.transparent)
    painter = QPainter(stacked)
    y = 0
    for piece in pieces:
        painter.drawPixmap((width - piece.width()) // 2, y, piece)
        y += piece.height() + gap
    painter.end()
    return stacked


# ---- dialog pieces (confirm, report) ----
DIALOG_BUTTON_MIN_HEIGHT = 40
DIALOG_BUTTON_MIN_WIDTH = 120
HEADER_HEADING_FONT_SIZE = 15
HEADER_SUBHEADING_FONT_SIZE = 11
HEADER_COLUMN_SPACING = 14
HEADER_SEPARATOR_GAP = 2


def MakeButton(text: str, primary: bool = False) -> QPushButton:
    """A dialog button: a comfortable click target, and the default (Enter) one when primary."""
    button = QPushButton(text)
    button.setMinimumHeight(DIALOG_BUTTON_MIN_HEIGHT)
    button.setMinimumWidth(DIALOG_BUTTON_MIN_WIDTH)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setProperty("primary", True)
        button.setDefault(True)
    return button


@dataclass(frozen=True)
class HeaderLayout:
    artWidth: int
    artMaxHeight: int
    spacing: int
    rowSpacing: int
    labelMinWidth: int
    artAlignment: Qt.AlignmentFlag
    boldValues: bool


def DetailHeader(details: dict, layout: HeaderLayout) -> QWidget:
    """The art beside {heading, subheading, rows[{label, value}], note} that AHK sends as fields."""
    wrap = QWidget()
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(layout.spacing)
    art = _HeaderArt(details.get("image", ""), layout)
    if art is not None:
        row.addWidget(art, 0, layout.artAlignment)

    col = QVBoxLayout()
    col.setSpacing(layout.rowSpacing)
    titled = _AddHeaderTitles(col, details)
    rows = details.get("rows") or []
    if titled and (rows or details.get("note")):
        col.addSpacing(HEADER_SEPARATOR_GAP)
        col.addWidget(Separator())
    if rows:
        col.addLayout(_HeaderRows(rows, layout))
    # A warning earns colour; everything else here is neutral detail. The
    # palette has no warn entry, so this uses the theme's own accent role.
    if details.get("note"):
        note = QLabel(str(details["note"]))
        note.setWordWrap(True)
        note.setProperty("role", "accent")
        ApplyFont(note, gc.APP_FONT_POINT_SIZE, bold=True)
        col.addWidget(note)
    col.addStretch(1)
    row.addLayout(col, 1)
    return wrap


def _HeaderArt(path: str, layout: HeaderLayout) -> QLabel | None:
    pixmap = QPixmap(path) if path else None
    if pixmap is None or pixmap.isNull():
        return None
    # the art is a transparent sheet, often two icons side by side - crop and
    # stack them so they fill the tall slot instead of floating in it; the width
    # drives the size, with a height ceiling so a tall sheet cannot stretch the dialog
    pixmap = StackSprites(pixmap)
    scaled = pixmap.scaledToWidth(layout.artWidth, Qt.TransformationMode.SmoothTransformation)
    if scaled.height() > layout.artMaxHeight:
        scaled = pixmap.scaledToHeight(layout.artMaxHeight, Qt.TransformationMode.SmoothTransformation)
    art = QLabel()
    art.setPixmap(scaled)
    art.setAlignment(Qt.AlignmentFlag.AlignHCenter | layout.artAlignment)
    return art


def _AddHeaderTitles(col: QVBoxLayout, details: dict) -> bool:
    if details.get("heading"):
        heading = QLabel(str(details["heading"]))
        heading.setWordWrap(True)
        ApplyFont(heading, HEADER_HEADING_FONT_SIZE, bold=True)
        col.addWidget(heading)
    if details.get("subheading"):
        sub = QLabel(str(details["subheading"]))
        sub.setWordWrap(True)
        sub.setProperty("subtle", True)
        ApplyFont(sub, HEADER_SUBHEADING_FONT_SIZE)
        col.addWidget(sub)
    return bool(details.get("heading") or details.get("subheading"))


def _HeaderRows(rows: list, layout: HeaderLayout) -> QGridLayout:
    grid = QGridLayout()
    grid.setHorizontalSpacing(HEADER_COLUMN_SPACING)
    grid.setVerticalSpacing(layout.rowSpacing)
    grid.setColumnMinimumWidth(0, layout.labelMinWidth)
    grid.setColumnStretch(1, 1)
    for index, entry in enumerate(rows):
        name = QLabel(str(entry.get("label", "")))
        name.setProperty("subtle", True)
        ApplyFont(name, gc.APP_FONT_POINT_SIZE)
        value = QLabel(str(entry.get("value", "")))
        value.setWordWrap(True)
        ApplyFont(value, gc.APP_FONT_POINT_SIZE, bold=layout.boldValues)
        grid.addWidget(name, index, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value, index, 1, Qt.AlignmentFlag.AlignTop)
    return grid
