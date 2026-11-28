from __future__ import annotations

import ctypes
import sys
import re
from dataclasses import dataclass

from automaton_gui.framework import KeyNames

PASSTHROUGH = "~"
GAME_KEY_MODIFIERS = "^!+"
GAME_KEY_NAMED = {
    name.lower(): name
    for name in ("Tab", "Enter", "Space", "Backspace", "Delete", "Insert", "Home", "End", "PgUp", "PgDn", "Up", "Down",
                 "Left", "Right", "CapsLock", "NumLock", "ScrollLock", "PrintScreen", "Pause", "AppsKey")
}
PASSTHROUGH_CHARS = "~*$"
MODIFIER_ORDER = "^!+#"
MODIFIER_NAMES = {"^": "Ctrl", "!": "Alt", "+": "Shift", "#": "Win"}
COMBO_SEPARATOR = " & "
LABEL_SEPARATOR = " + "

VK_MODIFIER_SYMBOL = {0x10: "+", 0x11: "^", 0x12: "!", 0x5B: "#", 0x5C: "#"}
VK_ESCAPE = 0x1B
OEM_VK_RANGES = ((0xBA, 0xC0), (0xDB, 0xDF), (0xE2, 0xE2))
MOUSE_KEYS = {"rbutton": 2, "mbutton": 3, "xbutton1": 4, "xbutton2": 5}
MOUSE_KEY_NAMES = {2: "RButton", 3: "MButton", 4: "XButton1", 5: "XButton2"}
LONE_MODIFIER_NAMES = {"shift", "ctrl", "alt", "lwin", "rwin"}

FIXED_LABELS = {
    "printscreen": "Print Screen",
    "pause": "Pause",
    **{name.lower(): label for name, (_vk, label, _qtKey) in KeyNames.MEDIA_KEYS.items()},
}

_NAV_KEYS = {
    "Insert": 0x2D,
    "Delete": 0x2E,
    "End": 0x23,
    "Down": 0x28,
    "PgDn": 0x22,
    "Left": 0x25,
    "Right": 0x27,
    "Home": 0x24,
    "Up": 0x26,
    "PgUp": 0x21,
}
_NUMPAD_NAV_KEYS = {
    "NumpadIns": 0x2D,
    "NumpadDel": 0x2E,
    "NumpadEnd": 0x23,
    "NumpadDown": 0x28,
    "NumpadPgDn": 0x22,
    "NumpadLeft": 0x25,
    "NumpadClear": 0x0C,
    "NumpadRight": 0x27,
    "NumpadHome": 0x24,
    "NumpadUp": 0x26,
    "NumpadPgUp": 0x21,
}
_PLAIN_KEYS = {
    "Space": 0x20,
    "Tab": 0x09,
    "Backspace": 0x08,
    "CapsLock": 0x14,
    "ScrollLock": 0x91,
    "Pause": 0x13,
    "NumpadMult": 0x6A,
    "NumpadAdd": 0x6B,
    "NumpadSub": 0x6D,
    "NumpadDot": 0x6E,
    **{name: vk for name, (vk, _label, _qtKey) in KeyNames.MEDIA_KEYS.items()},
}
_EXTENDED_ONLY_KEYS = {
    "NumpadDiv": 0x6F,
    "NumpadEnter": 0x0D,
    "NumLock": 0x90,
    "PrintScreen": 0x2C,
    "AppsKey": 0x5D,
}


def _BuildKeyTables() -> tuple[dict[str, tuple[int, bool | None]], dict[tuple[int, bool | None], str]]:
    byName: dict[str, tuple[int, bool | None]] = {}
    for letter in range(ord("A"), ord("Z") + 1):
        byName[chr(letter)] = (letter, None)
    for digit in range(10):
        byName[str(digit)] = (ord("0") + digit, None)
        byName[f"Numpad{digit}"] = (0x60 + digit, None)
    for number in range(1, 25):
        byName[f"F{number}"] = (0x6F + number, None)
    for name, vk in _NAV_KEYS.items():
        byName[name] = (vk, True)
    for name, vk in _NUMPAD_NAV_KEYS.items():
        byName[name] = (vk, False)
    for name, vk in _PLAIN_KEYS.items():
        byName[name] = (vk, None)
    for name, vk in _EXTENDED_ONLY_KEYS.items():
        byName[name] = (vk, True)
    byName["Enter"] = (0x0D, False)
    byVk: dict[tuple[int, bool | None], str] = {}
    for name, entry in byName.items():
        byVk[entry] = name
    return byName, byVk


_VK_BY_NAME, _NAME_BY_VK = _BuildKeyTables()
_LOWER_VK_BY_NAME = {name.lower(): entry for name, entry in _VK_BY_NAME.items()}
_RAW_VK = re.compile(r"^vk([0-9a-f]{2})$", re.IGNORECASE)
_HOTKEY = re.compile(r"^(?P<prefix>[~*$]*)(?P<modifiers>[\^!+#]*)(?P<key>\S+)$")


@dataclass(frozen=True)
class Hotkey:
    key: str
    modifiers: str = ""
    comboKey: str = ""
    prefix: str = ""

    def ToAhk(self) -> str:
        if self.comboKey:
            return f"{self.prefix}{self.key}{COMBO_SEPARATOR}{self.comboKey}"
        return f"{self.prefix}{self.modifiers}{self.key}"

    def Identity(self) -> tuple[str, str, str]:
        return (
            "".join(sorted(self.modifiers)),
            self.key.lower(),
            self.comboKey.lower(),
        )

    def Labels(self) -> list[str]:
        parts = [ModifierLabel(symbol) for symbol in self.modifiers]
        parts.append(KeyLabel(self.key))
        if self.comboKey:
            parts.append(KeyLabel(self.comboKey))
        return parts

    def Display(self) -> str:
        return LABEL_SEPARATOR.join(self.Labels())

    def WithPrefix(self, prefix: str) -> Hotkey:
        return Hotkey(self.key, self.modifiers, self.comboKey, prefix)


def Parse(value: str) -> Hotkey | None:
    text = value.strip()
    if COMBO_SEPARATOR.strip() in text:
        return _ParseCombo(text)
    match = _HOTKEY.match(text)
    if match is None or not _KnownKey(match["key"]):
        return None
    modifiers = "".join(symbol for symbol in MODIFIER_ORDER if symbol in match["modifiers"])
    return Hotkey(match["key"], modifiers, "", match["prefix"])


def _ParseCombo(text: str) -> Hotkey | None:
    left, _, right = (part.strip() for part in text.partition("&"))
    prefix = ""
    while left and left[0] in PASSTHROUGH_CHARS:
        prefix += left[0]
        left = left[1:]
    if not (_KnownKey(left) and _KnownKey(right)):
        return None
    return Hotkey(left, "", right, prefix)


def _KnownKey(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in _LOWER_VK_BY_NAME
        or lowered in MOUSE_KEYS
        or lowered in LONE_MODIFIER_NAMES
        or _RAW_VK.match(name) is not None
    )


def PrefixOf(value: str) -> str:
    return re.match(r"^[~*$]*", value.strip())[0]


def EnsurePassthrough(value: str) -> str:
    text = value.strip()
    if not text or PASSTHROUGH in PrefixOf(text):
        return text
    return PASSTHROUGH + text


def IsLoneModifier(hotkey: Hotkey) -> bool:
    return not hotkey.comboKey and hotkey.key.lower() in LONE_MODIFIER_NAMES


def GameKeyValue(hotkey: Hotkey, allowModifiers: bool = False) -> str | None:
    if hotkey.comboKey:
        return None
    if hotkey.modifiers and not (allowModifiers and all(symbol in GAME_KEY_MODIFIERS for symbol in hotkey.modifiers)):
        return None
    key = _GameKeyName(hotkey.key)
    if key is None or (hotkey.modifiers and key in ("LWin", "RWin")):
        return None
    return hotkey.modifiers + key


def _GameKeyName(name: str) -> str | None:
    lowered = name.lower()
    if len(lowered) == 1 and lowered.isascii() and lowered.isalnum():
        return lowered
    if lowered in ("lwin", "rwin"):
        return "LWin" if lowered == "lwin" else "RWin"
    functionKey = re.fullmatch(r"f(\d{1,2})", lowered)
    if functionKey and 1 <= int(functionKey[1]) <= 24:
        return f"F{int(functionKey[1])}"
    if lowered in GAME_KEY_NAMED:
        return GAME_KEY_NAMED[lowered]
    raw = _RAW_VK.match(name)
    return _LayoutKeyName(int(raw[1], 16)) if raw else None


# Punctuation keys stay as vkXX: their character changes per layout and some are dead keys (^ on German).
def _LayoutKeyName(vk: int) -> str | None:
    if any(low <= vk <= high for low, high in OEM_VK_RANGES):
        return f"vk{vk:02X}"
    return None


def ModifierLabel(symbol: str) -> str:
    return _ModifierName(MODIFIER_NAMES[symbol])


def _ModifierName(english: str) -> str:
    return KeyNames.TranslatedName(english, english)


def KeyLabel(name: str) -> str:
    lowered = name.lower()
    if lowered in MOUSE_KEYS:
        return KeyNames.MousePattern().format(number=MOUSE_KEYS[lowered])
    if lowered in ("shift", "ctrl", "alt"):
        return _ModifierName(lowered.capitalize())
    if lowered in FIXED_LABELS:
        return KeyNames.TranslatedName(lowered, FIXED_LABELS[lowered])
    entry = _LOWER_VK_BY_NAME.get(lowered)
    if entry is None:
        raw = _RAW_VK.match(name)
        entry = (int(raw[1], 16), None) if raw else None
    if lowered in ("lwin", "rwin"):
        entry = (0x5B if lowered == "lwin" else 0x5C, True)
    localized = KeyNames.RestoreAccents(_WindowsKeyName(*entry)) if entry else ""
    return localized or name


def _WindowsKeyName(vk: int, extended: bool | None) -> str:
    if sys.platform != "win32":
        return ""
    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    if scan == 0:
        return ""
    lParam = (scan << 16) | ((1 << 24) if extended else 0)
    buffer = ctypes.create_unicode_buffer(64)
    if user32.GetKeyNameTextW(lParam, buffer, 64) == 0:
        return ""
    return " ".join(word.capitalize() for word in buffer.value.split())


def ModifierSymbolForVk(vk: int) -> str:
    return VK_MODIFIER_SYMBOL.get(vk, "")


def LoneModifierName(vk: int) -> str:
    return {0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt", 0x5B: "LWin", 0x5C: "RWin"}[vk]


def AhkKeyFromNative(vk: int, extended: bool) -> str | None:
    name = _NAME_BY_VK.get((vk, extended)) or _NAME_BY_VK.get((vk, None))
    if name is not None:
        return name
    if any(low <= vk <= high for low, high in OEM_VK_RANGES):
        return f"vk{vk:02X}"
    return None


def MouseKeyName(buttonNumber: int) -> str:
    return MOUSE_KEY_NAMES[buttonNumber]


class Capture:
    """Collects the keys held down between the first press and the last release."""

    def __init__(self) -> None:
        self._held: set[str] = set()
        self._modifierSymbols = ""
        self._loneModifiers: list[str] = []
        self._keys: list[str] = []

    @property
    def active(self) -> bool:
        return bool(self._held)

    def HoldsNothingButShift(self) -> bool:
        return (not self._keys) and (self._modifierSymbols in ("", "+"))

    def Press(self, token: str, vk: int, extended: bool = False) -> None:
        if token in self._held:
            return
        self._held.add(token)
        symbol = ModifierSymbolForVk(vk)
        if symbol:
            if symbol not in self._modifierSymbols:
                self._modifierSymbols += symbol
            name = LoneModifierName(vk)
            if name not in self._loneModifiers:
                self._loneModifiers.append(name)
            return
        name = AhkKeyFromNative(vk, extended)
        if name is not None and name not in self._keys:
            self._keys.append(name)

    def PressMouse(self, token: str, buttonNumber: int) -> None:
        if token in self._held:
            return
        self._held.add(token)
        name = MouseKeyName(buttonNumber)
        if name not in self._keys:
            self._keys.append(name)

    def Release(self, token: str) -> Hotkey | None:
        self._held.discard(token)
        if self._held:
            return None
        result = self._Resolve()
        self.Reset()
        return result

    def Reset(self) -> None:
        self._held.clear()
        self._modifierSymbols = ""
        self._loneModifiers = []
        self._keys = []

    def Preview(self) -> list[str]:
        symbols = [symbol for symbol in MODIFIER_ORDER if symbol in self._modifierSymbols]
        return [ModifierLabel(symbol) for symbol in symbols] + [KeyLabel(name) for name in self._keys]

    def _Resolve(self) -> Hotkey | None:
        modifiers = "".join(symbol for symbol in MODIFIER_ORDER if symbol in self._modifierSymbols)
        if not self._keys:
            if len(self._loneModifiers) == 1:
                return Hotkey(self._loneModifiers[0])
            return None
        if len(self._keys) == 1:
            return Hotkey(self._keys[0], modifiers)
        if len(self._keys) == 2 and not modifiers:
            return Hotkey(self._keys[0], "", self._keys[1])
        return None
