from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

from automaton_gui import GUIConstants as gc
from automaton_gui.theme.Palettes import Palette, Darken, HexOf, Mix

# The app-wide QSS built from one palette. Qt lets us drive the whole UI from one
# stylesheet string, so each control group below gets the same derived colors
# and BuildStylesheet concatenates the groups.


def _ArrowTriangle(size: int, direction: str) -> QPolygonF:
    """The arrow triangle for a `size` px square canvas (3..13 wide, 6..11 tall
    at 16 px)."""
    left = (size * 3) / 16
    right = size - left
    middle = size / 2
    base = (size * 6) / 16
    tip = (size * 11) / 16
    if direction == "up":
        base, tip = tip, base
    return QPolygonF([QPointF(left, base), QPointF(right, base), QPointF(middle, tip)])


def _ArrowPng(colorHex: str, direction: str = "down") -> str:
    """Render a small triangle of `colorHex` pointing `direction` ('down' or
    'up') to a cached PNG and return its forward-slash path for use as a QSS
    `image: url(...)`. Qt's CSS border-triangle trick renders as a filled box on
    these subcontrols, so we hand a real image instead. Cached per size, color
    and direction so repeated theme swaps do not re-render. Falls back to '' (no
    image) if Qt cannot paint headlessly."""
    size = gc.CHROME_ARROW_GLYPH_PX
    cacheDir = os.path.join(tempfile.gettempdir(), "automaton_gui_arrows")
    path = os.path.join(cacheDir, f"{direction}_{size}_{colorHex.lstrip('#')}.png")
    if os.path.exists(path):
        return path.replace("\\", "/")
    try:
        os.makedirs(cacheDir, exist_ok=True)
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colorHex))
        painter.drawPolygon(_ArrowTriangle(size, direction))
        painter.end()
        image.save(path, "PNG")
        return path.replace("\\", "/")
    except (OSError, RuntimeError):
        return ""


@dataclass(frozen=True)
class ChromeColors:
    """The palette as QSS color strings, plus the colors and arrow images derived
    from it."""

    bg: str
    surface: str
    surface2: str
    hover: str
    border: str
    sep: str
    text: str
    subtle: str
    accent: str
    accentHi: str
    primaryFg: str
    accentPressed: str
    selection: str
    disabledFg: str
    handle: str
    arrow: str
    arrowActive: str
    arrowUp: str

    @classmethod
    def Of(cls, p: Palette) -> ChromeColors:
        subtle = HexOf(p.subtle)
        accent = HexOf(p.accent)
        return cls(
            bg=HexOf(p.bg),
            surface=HexOf(p.surface),
            surface2=HexOf(p.surface2),
            hover=HexOf(p.hover),
            border=HexOf(p.border),
            sep=HexOf(p.sep),
            text=HexOf(p.text),
            subtle=subtle,
            accent=accent,
            accentHi=HexOf(p.accentHi),
            primaryFg=HexOf(p.primaryFg),
            accentPressed=HexOf(Darken(p.accent, 0.85)),
            # a faint accent tint for selection backgrounds that still reads on either mode
            selection=HexOf(Mix(p.surface, p.accent, 0.35)),
            disabledFg=HexOf(Mix(p.text, p.bg, 0.55)),
            handle=HexOf(Mix(p.bg, p.subtle, 0.5)),
            arrow=_ArrowPng(subtle),
            arrowActive=_ArrowPng(accent),
            arrowUp=_ArrowPng(subtle, "up"),
        )


def _BaseRules(c: ChromeColors) -> str:
    return f"""
    QWidget {{
        background-color: {c.bg};
        color: {c.text};
    }}
    QMainWindow, QDialog {{
        background-color: {c.bg};
    }}
    QLabel, QCheckBox, QRadioButton, QGroupBox {{
        background-color: transparent;
    }}
    QLabel[subtle="true"] {{
        color: {c.subtle};
    }}
    QLabel[role="accent"] {{
        color: {c.accent};
    }}"""


def _ButtonRules(c: ChromeColors) -> str:
    return f"""
    QPushButton {{
        background-color: {c.surface2};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {gc.CHROME_BUTTON_RADIUS}px;
        padding: {gc.CHROME_BUTTON_PADDING};
    }}
    QPushButton:hover {{
        background-color: {c.hover};
    }}
    QPushButton:pressed {{
        background-color: {c.sep};
    }}
    QPushButton:disabled {{
        color: {c.disabledFg};
    }}
    QPushButton[primary="true"] {{
        background-color: {c.accent};
        color: {c.primaryFg};
        border: 1px solid {c.accent};
        font-weight: 600;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {c.accentHi};
        border-color: {c.accentHi};
    }}
    QPushButton[primary="true"]:pressed {{
        background-color: {c.accentPressed};
        border-color: {c.accentPressed};
    }}
    QPushButton[primary="true"]:disabled {{
        background-color: {c.surface2};
        color: {c.disabledFg};
        border-color: {c.border};
    }}
    QPushButton[chip="true"] {{
        background-color: {c.surface};
        border-radius: {gc.CHROME_BUTTON_RADIUS}px;
        padding: 0px;
    }}
    QPushButton[chip="true"]:hover {{
        background-color: {c.hover};
    }}
    QPushButton[chip="true"]:checked {{
        background-color: {c.accent};
        border-color: {c.accent};
    }}
    QPushButton[chip="true"][focused="true"] {{
        border: 2px solid {c.accentHi};
    }}"""


def _InputRules(c: ChromeColors) -> str:
    return f"""
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {gc.CHROME_INPUT_RADIUS}px;
        padding: {gc.CHROME_INPUT_PADDING};
        selection-background-color: {c.accent};
        selection-color: {c.primaryFg};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {c.accent};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        color: {c.disabledFg};
    }}"""


def _ComboAndListRules(c: ChromeColors) -> str:
    return f"""
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: {gc.CHROME_COMBO_DROPDOWN_WIDTH}px;
        border-left: 1px solid {c.border};
        border-top-right-radius: {gc.CHROME_INPUT_RADIUS}px;
        border-bottom-right-radius: {gc.CHROME_INPUT_RADIUS}px;
        background-color: {c.surface2};
    }}
    QComboBox::drop-down:hover {{
        background-color: {c.hover};
    }}
    QComboBox::down-arrow {{
        image: url({c.arrow});
        width: {gc.CHROME_COMBO_ARROW_SIZE}px;
        height: {gc.CHROME_COMBO_ARROW_SIZE}px;
    }}
    QComboBox::down-arrow:on {{
        image: url({c.arrowActive});
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        selection-background-color: {c.selection};
        selection-color: {c.text};
        outline: none;
    }}

    QListWidget {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        outline: none;
    }}
    QListWidget::item:selected {{
        background-color: {c.accent};
        color: {c.primaryFg};
    }}"""


def _SpinnerRules(c: ChromeColors) -> str:
    return f"""
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {c.surface2};
        border-left: 1px solid {c.border};
        width: {gc.CHROME_SPINNER_BUTTON_WIDTH}px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {c.hover};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url({c.arrowUp});
        width: {gc.CHROME_SPINNER_ARROW_SIZE}px;
        height: {gc.CHROME_SPINNER_ARROW_SIZE}px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url({c.arrow});
        width: {gc.CHROME_SPINNER_ARROW_SIZE}px;
        height: {gc.CHROME_SPINNER_ARROW_SIZE}px;
    }}"""


def _CheckAndGroupRules(c: ChromeColors) -> str:
    return f"""
    QCheckBox::indicator, QRadioButton::indicator {{
        width: {gc.CHROME_CHECKBOX_SIZE}px;
        height: {gc.CHROME_CHECKBOX_SIZE}px;
        border: 1px solid {c.border};
        border-radius: {gc.CHROME_CHECKBOX_RADIUS}px;
        background-color: {c.surface};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {c.accent};
        border-color: {c.accent};
    }}
    QRadioButton::indicator {{
        border-radius: {gc.CHROME_RADIO_RADIUS}px;
    }}

    QGroupBox {{
        border: 1px solid {c.border};
        border-radius: {gc.CHROME_GROUPBOX_RADIUS}px;
        margin-top: {gc.CHROME_GROUPBOX_MARGIN_TOP}px;
        padding: {gc.CHROME_GROUPBOX_PADDING}px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {gc.CHROME_GROUPBOX_TITLE_LEFT}px;
        padding: {gc.CHROME_GROUPBOX_TITLE_PADDING};
        color: {c.subtle};
    }}"""


def _TabRules(c: ChromeColors) -> str:
    return f"""
    QToolBox::tab {{
        background-color: {c.surface2};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {gc.CHROME_BUTTON_RADIUS}px;
        padding: {gc.CHROME_TOOLBOX_TAB_PADDING}px;
    }}
    QToolBox::tab:selected {{
        background-color: {c.hover};
        font-weight: 600;
    }}

    QTabWidget::pane {{
        border: none;
        border-top: 1px solid {c.border};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c.subtle};
        padding: {gc.CHROME_TAB_PADDING};
        border-bottom: {gc.CHROME_TAB_ACCENT_WIDTH}px solid transparent;
    }}
    QTabBar::tab:hover {{
        color: {c.text};
    }}
    QTabBar::tab:selected {{
        color: {c.text};
        font-weight: 600;
        border-bottom: {gc.CHROME_TAB_ACCENT_WIDTH}px solid {c.accent};
    }}"""


def _MenuRules(c: ChromeColors) -> str:
    return f"""
    QMenuBar {{
        background-color: {c.bg};
        color: {c.text};
        font-size: {gc.CHROME_MENU_FONT_SIZE}px;
        padding: 2px 4px;
    }}
    QMenuBar::item {{
        padding: {gc.CHROME_MENUBAR_ITEM_PADDING};
        border-radius: {gc.CHROME_BUTTON_RADIUS}px;
    }}
    QMenuBar::item:selected {{
        background-color: {c.hover};
    }}
    QMenu {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        font-size: {gc.CHROME_MENU_FONT_SIZE}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: {gc.CHROME_MENU_ITEM_PADDING};
        border-radius: {gc.CHROME_BUTTON_RADIUS}px;
    }}
    QMenu::item:selected {{
        background-color: {c.selection};
    }}
    QMenu::separator {{
        height: {gc.CHROME_MENU_SEPARATOR_HEIGHT}px;
        background-color: {c.sep};
        margin: {gc.CHROME_MENU_SEPARATOR_MARGIN};
    }}"""


def _ScrollRules(c: ChromeColors) -> str:
    return f"""
    QScrollArea {{
        border: none;
        background-color: {c.bg};
    }}
    QScrollBar:vertical {{
        background-color: {c.bg};
        width: {gc.CHROME_SCROLLBAR_SIZE}px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c.handle};
        border-radius: {gc.CHROME_SCROLLBAR_HANDLE_RADIUS}px;
        min-height: {gc.CHROME_SCROLLBAR_HANDLE_MIN}px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {c.subtle};
    }}
    QScrollBar:horizontal {{
        background-color: {c.bg};
        height: {gc.CHROME_SCROLLBAR_SIZE}px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c.handle};
        border-radius: {gc.CHROME_SCROLLBAR_HANDLE_RADIUS}px;
        min-width: {gc.CHROME_SCROLLBAR_HANDLE_MIN}px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {c.subtle};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0;
        height: 0;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}"""


def _TooltipAndSeparatorRules(c: ChromeColors) -> str:
    return f"""
    QToolTip {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
    }}

    QFrame[role="separator"] {{
        background-color: {c.sep};
    }}"""


_RULE_GROUPS = (
    _BaseRules,
    _ButtonRules,
    _InputRules,
    _ComboAndListRules,
    _SpinnerRules,
    _CheckAndGroupRules,
    _TabRules,
    _MenuRules,
    _ScrollRules,
    _TooltipAndSeparatorRules,
)


def BuildStylesheet(p: Palette) -> str:
    colors = ChromeColors.Of(p)
    return "\n".join(group(colors) for group in _RULE_GROUPS) + "\n    "
