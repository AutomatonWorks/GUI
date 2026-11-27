from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QApplication, QWidget

from automaton_gui import GUIConstants as gc
from automaton_gui.theme import Palettes
from automaton_gui.theme.Palettes import Palette
from automaton_gui.theme.Stylesheet import BuildStylesheet

# Theming engine ported from guis/framework/Theme.ahk2. The AHK Theme only held
# colors; per-control chrome was applied widget-by-widget. Qt lets us drive the
# whole UI from one QSS string built from the active palette, so this engine:
#   * builds a QSS stylesheet per palette (hand-rolled, palette-driven, no extra
#     dependency - chosen over qdarktheme/qt-material so the named palettes stay
#     the single source of truth),
#   * applies it app-wide and swaps it live on SetMode,
#   * sets the Win11 dark title bar (DwmSetWindowAttribute) per top-level window,
#   * sets the OS app-mode (uxtheme SetPreferredAppMode) so menus/popups follow.


class ThemeEngine:
    """Holds the active palette and applies it to a QApplication + windows."""

    def __init__(self, mode: str = Palettes.DEFAULT) -> None:
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def palette(self) -> Palette:
        return Palettes.Get(self._mode)

    @property
    def isDark(self) -> bool:
        return self.palette.dark

    def Stylesheet(self, mode: str | None = None) -> str:
        pal = Palettes.Get(mode) if mode is not None else self.palette
        return BuildStylesheet(pal)

    def Apply(self, app: QApplication | None = None, mode: str | None = None) -> None:
        """Apply the active (or given) palette app-wide: stylesheet + OS app-mode
        + dark title bar on every existing top-level window."""
        if mode is not None:
            self._mode = mode
        app = app or QApplication.instance()
        if app is not None:
            font = app.font()
            font.setPointSize(gc.APP_FONT_POINT_SIZE)
            app.setFont(font)
            app.setStyleSheet(self.Stylesheet())
        self._ApplyAppMode()
        for window in QApplication.topLevelWidgets():
            self.ApplyTitlebar(window)

    def SetMode(self, mode: str) -> None:
        """Switch the active palette live (stylesheet + chrome re-applied)."""
        if not Palettes.Has(mode):
            raise KeyError(mode)
        self._mode = Palettes.Get(mode).name
        self.Apply()

    def ApplyTitlebar(self, widget: QWidget) -> None:
        """Set the light/dark title bar for one top-level window (Win11 attr 20,
        Win10 attr 19 fallback). Harmless no-op off Windows / offscreen."""
        if sys.platform != "win32":
            return
        try:
            hwnd = int(widget.winId())
        except (RuntimeError, ValueError):
            return
        if not hwnd:
            return
        value = ctypes.c_int(1 if self.isDark else 0)
        try:
            dwm = ctypes.windll.dwmapi
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_PRE20H1 = 19
            res = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
            if res != 0:
                dwm.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE_PRE20H1,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except (OSError, AttributeError):
            pass

    def _ApplyAppMode(self) -> None:
        """uxtheme SetPreferredAppMode (ordinal 135): ForceDark=2, ForceLight=3,
        so menus/popups/native chrome follow the palette. Best-effort."""
        if sys.platform != "win32":
            return
        try:
            uxtheme = ctypes.WinDLL("uxtheme")
            prototype = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)
            setPreferredAppMode = prototype((135, uxtheme))
            setPreferredAppMode(2 if self.isDark else 3)
        except (OSError, ValueError, AttributeError):
            pass


theme = ThemeEngine()
