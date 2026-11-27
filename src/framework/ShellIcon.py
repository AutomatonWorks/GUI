from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtGui import QImage, QPixmap

# Pull native Windows shell icons (the shutdown / sleep glyphs) out of the system
# DLLs so a dialog can show the same icon the Start menu power button uses, instead
# of shipping our own art. ExtractIconEx hands back an HICON; Qt6 dropped QtWin, so
# we walk the icon's color bitmap through GetDIBits into a QImage by hand.
#
# Named icons resolve to a (dll, index) picked by eye from the sheets in this repo's
# audit notes: shell32 #27 is the red power button, imageres #96 the monitor+moon.
_ICON_SOURCES = {
    "shutdown": ("shell32.dll", 27),
    "sleep": ("imageres.dll", 96),
}


class _ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _Bind():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(_ICONINFO)]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(_BITMAPINFO),
        wintypes.UINT,
    ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    shell32.ExtractIconExW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(wintypes.HICON),
        ctypes.POINTER(wintypes.HICON),
        wintypes.UINT,
    ]
    return user32, gdi32, shell32


def _HiconToPixmap(user32, gdi32, hicon: int, size: int) -> QPixmap:
    info = _ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(info)):
        return QPixmap()
    hdc = user32.GetDC(0)
    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB
    buf = (ctypes.c_char * (size * size * 4))()
    scanlines = gdi32.GetDIBits(hdc, info.hbmColor, 0, size, buf, ctypes.byref(bmi), 0)
    user32.ReleaseDC(0, hdc)
    if info.hbmColor:
        gdi32.DeleteObject(info.hbmColor)
    if info.hbmMask:
        gdi32.DeleteObject(info.hbmMask)
    if not scanlines:
        return QPixmap()
    image = QImage(bytes(buf), size, size, QImage.Format.Format_ARGB32).copy()
    return QPixmap.fromImage(image)


def LoadShellIcon(name: str, size: int = 32) -> QPixmap:
    """Return the named Windows shell icon ('shutdown' / 'sleep') as a QPixmap, or an
    empty QPixmap when unknown or on any extraction failure (so the caller just draws
    no icon rather than crashing)."""
    source = _ICON_SOURCES.get(name)
    if source is None:
        return QPixmap()
    dll, index = source
    try:
        user32, gdi32, shell32 = _Bind()
        path = os.path.join(os.environ["SystemRoot"], "System32", dll)
        large = wintypes.HICON()
        count = shell32.ExtractIconExW(path, index, ctypes.byref(large), None, 1)
        if not count or not large.value:
            return QPixmap()
        try:
            return _HiconToPixmap(user32, gdi32, large.value, size)
        finally:
            user32.DestroyIcon(large)
    except OSError:
        return QPixmap()
