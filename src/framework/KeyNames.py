from __future__ import annotations

import ctypes
import sys
import unicodedata
import warnings
from functools import lru_cache

from PySide6.QtCore import QKeyCombination, QLibraryInfo, QTranslator, Qt
from PySide6.QtGui import QKeySequence

LANGUAGE_ID_MASK = 0xFFFF
PRIMARY_LANGUAGE_MASK = 0x3FF
LOCALE_NAME_LENGTH = 85
ENGLISH_LANGUAGE_ID = 0x0409
SHORTCUT_CONTEXT = "QShortcut"
FIRST_SPECIAL_KEY = 0x01000000
SPANISH = 0x0A

# Multimedia keys: AHK name -> (virtual key, English label, Qt key)
MEDIA_KEYS = {
    "Volume_Down": (0xAE, "Volume Down", Qt.Key.Key_VolumeDown),
    "Volume_Up": (0xAF, "Volume Up", Qt.Key.Key_VolumeUp),
    "Volume_Mute": (0xAD, "Volume Mute", Qt.Key.Key_VolumeMute),
    "Media_Next": (0xB0, "Media Next", Qt.Key.Key_MediaNext),
    "Media_Prev": (0xB1, "Media Previous", Qt.Key.Key_MediaPrevious),
    "Media_Stop": (0xB2, "Media Stop", Qt.Key.Key_MediaStop),
    "Media_Play_Pause": (0xB3, "Media Play/Pause", Qt.Key.Key_MediaTogglePlayPause),
    "Launch_Mail": (0xB4, "Launch Mail", Qt.Key.Key_LaunchMail),
    "Launch_Media": (0xB5, "Launch Media", Qt.Key.Key_LaunchMedia),
    "Launch_App1": (0xB6, "Launch App 1", Qt.Key.Key_Launch0),
    "Launch_App2": (0xB7, "Launch App 2", Qt.Key.Key_Launch1),
    "Browser_Back": (0xA6, "Browser Back", Qt.Key.Key_Back),
    "Browser_Forward": (0xA7, "Browser Forward", Qt.Key.Key_Forward),
    "Browser_Refresh": (0xA8, "Browser Refresh", Qt.Key.Key_Refresh),
    "Browser_Stop": (0xA9, "Browser Stop", Qt.Key.Key_Stop),
    "Browser_Search": (0xAA, "Browser Search", Qt.Key.Key_Search),
    "Browser_Favorites": (0xAB, "Browser Favorites", Qt.Key.Key_Favorites),
    "Browser_Home": (0xAC, "Browser Home", Qt.Key.Key_HomePage),
}

QT_KEYS = {
    "shift": Qt.Key.Key_Shift,
    "ctrl": Qt.Key.Key_Control,
    "alt": Qt.Key.Key_Alt,
    "printscreen": Qt.Key.Key_Print,
    "pause": Qt.Key.Key_Pause,
    **{name.lower(): qtKey for name, (_vk, _label, qtKey) in MEDIA_KEYS.items()},
}

# Words Windows and Qt leave without their accents for one language, and what its mouse buttons are called
LANGUAGE_EXTRAS = {
    SPANISH: {
        "words": {
            "numero": "Número",
            "adicion": "Adición",
            "division": "División",
            "multiplicacion": "Multiplicación",
            "sustraccion": "Sustracción",
            "tabulacion": "Tabulación",
            "de": "de",
        },
        "mouse": "Ratón {number}",
    }
}


def KeyboardLanguageId() -> int:
    if sys.platform != "win32":
        return ENGLISH_LANGUAGE_ID
    user32 = ctypes.windll.user32
    user32.GetKeyboardLayout.restype = ctypes.c_size_t
    return user32.GetKeyboardLayout(0) & LANGUAGE_ID_MASK


def _Extras(languageId: int) -> dict:
    return LANGUAGE_EXTRAS.get(languageId & PRIMARY_LANGUAGE_MASK, {})


def _StripAccents(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").lower()


@lru_cache(maxsize=None)
def _Translator(languageId: int) -> QTranslator | None:
    if sys.platform != "win32":
        return None
    buffer = ctypes.create_unicode_buffer(LOCALE_NAME_LENGTH)
    if ctypes.windll.kernel32.LCIDToLocaleName(languageId, buffer, LOCALE_NAME_LENGTH, 0) == 0:
        return None
    full = buffer.value.replace("-", "_")
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for candidate in (full, full.split("_")[0]):
        translator = QTranslator()
        if translator.load(f"qtbase_{candidate}", path):
            return translator
    return None


def _QtName(qtKey: Qt.Key, languageId: int) -> tuple[str, str]:
    english = QKeySequence(QKeyCombination(qtKey)).toString(QKeySequence.SequenceFormat.NativeText)
    translator = _Translator(languageId)
    translated = translator.translate(SHORTCUT_CONTEXT, english) if translator is not None else ""
    return english, translated or english


def TranslatedName(name: str, default: str) -> str:
    qtKey = QT_KEYS.get(name.lower())
    if qtKey is None:
        return default
    english, translated = _QtName(qtKey, KeyboardLanguageId())
    return default if translated == english else translated


def MousePattern() -> str:
    return _Extras(KeyboardLanguageId()).get("mouse", "Mouse {number}")


@lru_cache(maxsize=None)
def _AccentWords(languageId: int) -> dict[str, str]:
    words: dict[str, str] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for qtKey in (key for key in Qt.Key if key.value >= FIRST_SPECIAL_KEY):
            _, translated = _QtName(qtKey, languageId)
            for word in translated.replace("+", " ").split():
                if _StripAccents(word) != word.lower():
                    words[_StripAccents(word)] = word[0].upper() + word[1:]
    words.update(_Extras(languageId).get("words", {}))
    return words


def RestoreAccents(label: str) -> str:
    words = _AccentWords(KeyboardLanguageId())
    return " ".join(words.get(_StripAccents(word), word) for word in label.split())
