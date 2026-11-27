from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable, Iterable

from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication, QWidget

# Window anchoring ported from guis/framework/Window.ahk2 (the GuiWindow.Anchor
# provider) + LibScreen.GameClientAnchor. AHK kept a static `GuiWindow.Anchor`
# func returning {x, y, w, h}; the host set it once to center every window over
# the running game client, else over the primary monitor work area. Same idea
# here: a module-level settable provider returning an (x, y, w, h) rect, used to
# center windows. The host wires in a game-window finder; the default is the
# primary screen work area (so a window opened before the game exists still lands
# on screen instead of a 0,0 box).

Rect = tuple[int, int, int, int]
Provider = Callable[[], Rect]

_provider: Provider | None = None


def SetAnchorProvider(provider: Provider | None) -> None:
    """Set the global anchor provider (a callable returning an (x, y, w, h) rect),
    or None to fall back to the primary work area. Mirrors `GuiWindow.Anchor`."""
    global _provider
    _provider = provider


def CurrentAnchor() -> Rect:
    """The active anchor rect: the provider's, else the primary work area."""
    provider = _provider or PrimaryWorkArea
    return provider()


def PrimaryWorkArea() -> Rect:
    """The primary screen's work area (desktop minus taskbar) as (x, y, w, h)."""
    app = QApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    if screen is not None:
        geometry = screen.availableGeometry()
        return (geometry.x(), geometry.y(), geometry.width(), geometry.height())
    return (0, 0, 1920, 1080)


def WindowRect(hwnd: int) -> Rect | None:
    """A foreign window's screen rect as (x, y, w, h) via Win32 GetWindowRect,
    or None if it can't be read (off-Windows, no hwnd, gone). ctypes, no pywin32
    import (same path style as theme.py)."""
    if sys.platform != "win32" or not hwnd:
        return None
    rect = wintypes.RECT()
    ok = ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    if not ok:
        return None
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def LogicalRect(rect: Rect, screens: Iterable[QScreen]) -> Rect:
    """A physical-pixel rect (what GetWindowRect returns) in Qt's logical
    coordinates, scaled by the devicePixelRatio of the screen holding its center.
    Qt keeps each screen's top-left in physical pixels and scales only the
    offsets inside it. Unchanged when no screen holds it."""
    x, y, w, h = rect
    centerX = x + (w // 2)
    centerY = y + (h // 2)
    for screen in screens:
        geometry = screen.geometry()
        ratio = screen.devicePixelRatio()
        left = geometry.x()
        top = geometry.y()
        insideX = left <= centerX < (left + (geometry.width() * ratio))
        insideY = top <= centerY < (top + (geometry.height() * ratio))
        if insideX and insideY:
            return (
                left + round((x - left) / ratio),
                top + round((y - top) / ratio),
                round(w / ratio),
                round(h / ratio),
            )
    return rect


def AnchorOverWindow(hwndGetter: Callable[[], int]) -> Provider:
    """Build a provider that anchors over the window returned by hwndGetter()
    when it's present, else the primary work area. The host passes a getter for
    the game window (the GameClientAnchor analogue); Python never reads the AHK
    game-detection logic - AHK sends the hwnd as `gameHwnd` in each show_*."""
    def Provider() -> Rect:
        hwnd = hwndGetter()
        if hwnd:
            rect = WindowRect(hwnd)
            if rect is not None:
                return LogicalRect(rect, QApplication.screens())
        return PrimaryWorkArea()
    return Provider


def ForceForeground(hwnd: int) -> None:
    """Force `hwnd` to the front AND give it focus, over a borderless-fullscreen
    game that owns the foreground. A background process (the GUI host is a child
    of AHK, not the foreground app) cannot SetForegroundWindow on its own: Windows'
    foreground lock blocks it, so a plain Qt raise_/activateWindow leaves the
    window stranded behind the game. The fix is the documented workaround:
    AttachThreadInput to the foreground thread so we share its input state (which
    satisfies SetForegroundWindow's caller check), plus a TOPMOST->NOTOPMOST toggle
    to lift the z-order without pinning the window always-on-top. No-op off Windows
    or when the window has no native handle yet (headless/offscreen)."""
    if sys.platform != "win32" or not hwnd:
        return
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    handle = wintypes.HWND(hwnd)
    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    try:
        foreground = user32.GetForegroundWindow()
        targetThread = user32.GetWindowThreadProcessId(foreground, None)
        thisThread = kernel32.GetCurrentThreadId()
        attached = bool(targetThread) and targetThread != thisThread
        if attached:
            user32.AttachThreadInput(targetThread, thisThread, True)
        user32.SetWindowPos(handle, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.SetWindowPos(handle, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        user32.BringWindowToTop(handle)
        user32.SetForegroundWindow(handle)
        if attached:
            user32.AttachThreadInput(targetThread, thisThread, False)
    except OSError:
        pass


def CenterWindow(window: QWidget, offsetX: int = 0, offsetY: int = 0) -> None:
    """Move `window` so it's centered over the current anchor rect (+ optional
    offset). Uses the window's current size, so call after it has been sized."""
    x, y, w, h = CurrentAnchor()
    px = x + (w - window.width()) // 2 + offsetX
    py = y + (h - window.height()) // 2 + offsetY
    window.move(px, py)
