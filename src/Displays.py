"""Connected monitors for the launch display dropdown.

Each display is keyed by its device interface path, which survives Windows renumbering
the screens. The AHK side (utils/LaunchDisplay.ahk2) finds the same path through
EnumDisplayDevices, and "Display N" follows EnumDisplayMonitors order, the same order
AHK's MonitorGet uses."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

# CI imports the GUI on Linux; only the display listing itself needs Windows.
_user32 = ctypes.WinDLL("user32") if (sys.platform == "win32") else None

_EDD_GET_DEVICE_INTERFACE_NAME = 1
_QDC_ONLY_ACTIVE_PATHS = 2
_GET_TARGET_NAME = 2


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _PathSource(ctypes.Structure):
    _fields_ = [("adapterId", _Luid), ("id", wintypes.UINT), ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT)]


class _Rational(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]


class _PathTarget(ctypes.Structure):
    _fields_ = [
        ("adapterId", _Luid), ("id", wintypes.UINT), ("modeInfoIdx", wintypes.UINT),
        ("outputTechnology", wintypes.UINT), ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
        ("refreshRate", _Rational), ("scanLineOrdering", wintypes.UINT), ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT),
    ]


class _PathInfo(ctypes.Structure):
    _fields_ = [("sourceInfo", _PathSource), ("targetInfo", _PathTarget), ("flags", wintypes.UINT)]


class _ModeInfo(ctypes.Structure):
    _fields_ = [("infoType", wintypes.UINT), ("id", wintypes.UINT), ("adapterId", _Luid), ("data", ctypes.c_byte * 48)]


class _DeviceInfoHeader(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT), ("adapterId", _Luid), ("id", wintypes.UINT)]


class _TargetName(ctypes.Structure):
    _fields_ = [
        ("header", _DeviceInfoHeader), ("flags", wintypes.UINT), ("outputTechnology", wintypes.UINT),
        ("edidManufactureId", wintypes.USHORT), ("edidProductCodeId", wintypes.USHORT),
        ("connectorInstance", wintypes.UINT), ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128),
    ]


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32),
    ]


class _DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32), ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD), ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128),
    ]


def _FriendlyNames() -> dict[str, str]:
    """Monitor device path (lower case) -> the name Windows shows, like "LG ULTRAGEAR"."""
    pathCount = wintypes.UINT()
    modeCount = wintypes.UINT()
    if _user32.GetDisplayConfigBufferSizes(_QDC_ONLY_ACTIVE_PATHS, ctypes.byref(pathCount), ctypes.byref(modeCount)) != 0:
        return {}
    paths = (_PathInfo * pathCount.value)()
    modes = (_ModeInfo * modeCount.value)()
    if _user32.QueryDisplayConfig(_QDC_ONLY_ACTIVE_PATHS, ctypes.byref(pathCount), paths, ctypes.byref(modeCount), modes, None) != 0:
        return {}
    names = {}
    for path in paths[: pathCount.value]:
        target = _TargetName()
        target.header.type = _GET_TARGET_NAME
        target.header.size = ctypes.sizeof(_TargetName)
        target.header.adapterId = path.targetInfo.adapterId
        target.header.id = path.targetInfo.id
        if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(target)) == 0:
            names[target.monitorDevicePath.lower()] = target.monitorFriendlyDeviceName
    return names


def _MonitorPath(gdiName: str) -> str:
    device = _DisplayDevice()
    device.cb = ctypes.sizeof(_DisplayDevice)
    if not _user32.EnumDisplayDevicesW(gdiName, 0, ctypes.byref(device), _EDD_GET_DEVICE_INTERFACE_NAME):
        return ""
    return device.DeviceID


def ListDisplays() -> list[tuple[str, str]]:
    """(device path, "Display N: Name") for every monitor, in EnumDisplayMonitors order."""
    if sys.platform != "win32":
        return []
    gdiNames: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def Collect(monitor, _hdc, _rect, _data):
        info = _MonitorInfoEx()
        info.cbSize = ctypes.sizeof(_MonitorInfoEx)
        if _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            gdiNames.append(info.szDevice)
        return True

    _user32.EnumDisplayMonitors(None, None, Collect, 0)
    friendly = _FriendlyNames()
    displays = []
    for number, gdiName in enumerate(gdiNames, start=1):
        path = _MonitorPath(gdiName)
        if path == "":
            continue
        name = friendly.get(path.lower()) or gdiName
        displays.append((path, f"Display {number}: {name}"))
    return displays
