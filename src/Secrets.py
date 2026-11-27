"""Passwords at rest, encrypted with Windows DPAPI: Windows keeps the key, tied to the Windows user, so nothing
secret is in the code. A value protected by another user or on another PC does not decrypt; Reveal gives "" and
the user types the password again."""

from __future__ import annotations

import base64
import binascii
import ctypes
import sys
from ctypes import wintypes

PREFIX = "dpapi:"
_ENTROPY = b"AutomatonWorks"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


# ctypes keeps the buffer alive through the cast pointer stored in the blob
def _BlobOf(data: bytes) -> _Blob:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _Dpapi(functionName: str, data: bytes) -> bytes | None:
    if sys.platform != "win32":
        raise OSError("DPAPI needs Windows")
    dataIn = _BlobOf(data)
    entropy = _BlobOf(_ENTROPY)
    dataOut = _Blob()
    function = getattr(ctypes.windll.crypt32, functionName)
    ok = function(ctypes.byref(dataIn), None, ctypes.byref(entropy), None, None,
                  _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(dataOut))
    if not ok:
        return None
    try:
        return ctypes.string_at(dataOut.pbData, dataOut.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(dataOut.pbData)


def _Encrypt(data: bytes) -> bytes:
    result = _Dpapi("CryptProtectData", data)
    if result is None:
        raise ctypes.WinError()
    return result


# None when this Windows user cannot decrypt it
def _Decrypt(data: bytes) -> bytes | None:
    return _Dpapi("CryptUnprotectData", data)


def IsProtected(stored: str) -> bool:
    return stored.startswith(PREFIX)


def Protect(text: str) -> str:
    if text == "":
        return ""
    return PREFIX + base64.b64encode(_Encrypt(text.encode("utf-8"))).decode("ascii")


# Plain text passes through, so a value typed by hand into the ini still works until the next start protects it.
def Reveal(stored: str) -> str:
    if not IsProtected(stored):
        return stored
    try:
        raw = base64.b64decode(stored[len(PREFIX):], validate=True)
    except binascii.Error:
        return ""
    plain = _Decrypt(raw)
    if plain is None:
        return ""
    return plain.decode("utf-8")
