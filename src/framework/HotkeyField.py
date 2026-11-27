from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from automaton_gui.framework import Hotkeys
from automaton_gui.framework.ErrorBubble import ErrorBubble
from automaton_gui.I18n import T

ICON_FONT_FAMILY = "Segoe MDL2 Assets"
ICON_FONT_SIZE = 11
ICON_BUTTON_STYLE = f"QPushButton {{ font-family: '{ICON_FONT_FAMILY}'; font-size: {ICON_FONT_SIZE}pt; padding: 0px; }}"
ICON_CLEAR = "\uE74D"
ICON_RESET = "\uE72C"
ICON_BUTTON_WIDTH = 34
ROW_SPACING = 6
EXTENDED_SCAN_MASK = 0xE000
NO_TOKEN_VK = 0
MOUSE_BUTTON_NUMBERS = {
    Qt.MouseButton.RightButton: 2,
    Qt.MouseButton.MiddleButton: 3,
    Qt.MouseButton.BackButton: 4,
    Qt.MouseButton.ForwardButton: 5,
}

ConflictChecker = Callable[[str], str]


class HotkeyEdit(QLineEdit):
    capturedValue = Signal(str)

    def __init__(
        self,
        strings: dict | None = None,
        gameKey: bool = False,
        allowModifiers: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._strings = strings
        self._gameKey = gameKey
        self._allowModifiers = allowModifiers
        self._value = ""
        self._listening = False
        self._capture = Hotkeys.Capture()
        self.setReadOnly(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.onCandidate: Callable[[str], bool] = lambda value: True
        self.onInvalid: Callable[[Hotkeys.Hotkey | None], None] = lambda hotkey: None
        self.prefixSource: Callable[[], str] = lambda: self._value
        self._ShowIdle()

    @property
    def listening(self) -> bool:
        return self._listening

    def value(self) -> str:
        return self._value

    def Normalize(self, value: str) -> str:
        return value.strip() if self._gameKey else Hotkeys.EnsurePassthrough(value)

    def SetValue(self, value: str) -> None:
        self._value = self.Normalize(value)
        if not self._listening:
            self._ShowIdle()

    def StartListening(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._capture.Reset()
        self.setText("")
        self.setPlaceholderText(self._Text("hotkey.press_keys", "Press a key or combination (Esc to cancel)"))

    def StopListening(self) -> None:
        self._listening = False
        self._capture.Reset()
        self._ShowIdle()

    def _Text(self, key: str, default: str) -> str:
        return T(self._strings, key, default)

    def _ShowIdle(self) -> None:
        parsed = Hotkeys.Parse(self._value)
        self.setText(parsed.Display() if parsed is not None else self._value)
        self.setPlaceholderText(self._Text("hotkey.not_set", "Click, then press a key"))

    def _ShowPreview(self) -> None:
        labels = self._capture.Preview()
        self.setText(Hotkeys.LABEL_SEPARATOR.join(labels))

    def _Finish(self, hotkey: Hotkeys.Hotkey | None) -> None:
        value = self._ValueFrom(hotkey) if hotkey is not None else None
        if value is None:
            self.onInvalid(hotkey)
            self._capture.Reset()
            self.setText("")
            return
        if not self.onCandidate(value):
            self.setText("")
            return
        self._value = value
        self.StopListening()
        self.capturedValue.emit(value)

    def _ValueFrom(self, hotkey: Hotkeys.Hotkey) -> str | None:
        if self._gameKey:
            return Hotkeys.GameKeyValue(hotkey, self._allowModifiers)
        if Hotkeys.IsLoneModifier(hotkey):
            return None
        return Hotkeys.EnsurePassthrough(hotkey.WithPrefix(Hotkeys.PrefixOf(self.prefixSource())).ToAhk())

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.StartListening()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.StopListening()

    def focusNextPrevChild(self, next_: bool) -> bool:
        if self._listening:
            return False
        return super().focusNextPrevChild(next_)

    def event(self, event: QEvent) -> bool:
        if self._listening and event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def mousePressEvent(self, event) -> None:
        button = event.button()
        if self._listening and button in MOUSE_BUTTON_NUMBERS:
            number = MOUSE_BUTTON_NUMBERS[button]
            self._capture.PressMouse(f"mouse{number}", number)
            self._ShowPreview()
            event.accept()
            return
        if not self._listening:
            self.StartListening()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        button = event.button()
        if self._listening and button in MOUSE_BUTTON_NUMBERS:
            self._Release(f"mouse{MOUSE_BUTTON_NUMBERS[button]}")
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if not self._listening:
            super().keyPressEvent(event)
            return
        event.accept()
        vk = event.nativeVirtualKey()
        if event.isAutoRepeat() or vk == NO_TOKEN_VK:
            return
        if vk == Hotkeys.VK_ESCAPE:
            self.StopListening()
            return
        extended = (event.nativeScanCode() & EXTENDED_SCAN_MASK) == EXTENDED_SCAN_MASK
        self._capture.Press(self._Token(vk, extended), vk, extended)
        self._ShowPreview()

    def keyReleaseEvent(self, event) -> None:
        if not self._listening:
            super().keyReleaseEvent(event)
            return
        event.accept()
        vk = event.nativeVirtualKey()
        if event.isAutoRepeat() or vk == NO_TOKEN_VK:
            return
        extended = (event.nativeScanCode() & EXTENDED_SCAN_MASK) == EXTENDED_SCAN_MASK
        self._Release(self._Token(vk, extended))

    def _Release(self, token: str) -> None:
        wasActive = self._capture.active
        hotkey = self._capture.Release(token)
        if self._capture.active:
            self._ShowPreview()
        elif wasActive:
            self._Finish(hotkey)

    @staticmethod
    def _Token(vk: int, extended: bool) -> str:
        return f"{vk}:{int(extended)}"


class HotkeyField(QWidget):
    valueChanged = Signal(str)

    def __init__(
        self,
        strings: dict | None = None,
        default: str = "",
        gameKey: bool = False,
        allowModifiers: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._strings = strings
        self._gameKey = gameKey
        self._conflictChecker: ConflictChecker | None = None

        self.edit = HotkeyEdit(strings, gameKey, allowModifiers)
        self._default = self.edit.Normalize(default)
        self.edit.onCandidate = self._AcceptCandidate
        self.edit.onInvalid = self._ShowInvalid
        self.edit.prefixSource = self._PrefixSource
        self.edit.capturedValue.connect(self._Captured)

        self.clearButton = self._IconButton(ICON_CLEAR, self._Text("hotkey.clear", "Clear"))
        self.clearButton.clicked.connect(self._Clear)
        if gameKey:
            self.clearButton.hide()
        self.resetButton = self._IconButton(ICON_RESET, "")
        self.resetButton.clicked.connect(self._Reset)

        self.warning = ErrorBubble(self)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ROW_SPACING)
        row.addWidget(self.edit, 1)
        row.addWidget(self.clearButton)
        row.addWidget(self.resetButton)

        self._RefreshButtons()

    def value(self) -> str:
        return self.edit.value()

    def SetValue(self, value: str) -> None:
        previous = self.edit.value()
        self.edit.SetValue(value)
        self._RefreshButtons()
        if self.edit.value() != previous:
            self.valueChanged.emit(self.edit.value())

    def SetDefault(self, default: str) -> None:
        self._default = self.edit.Normalize(default)
        self._RefreshButtons()

    def SetConflictChecker(self, checker: ConflictChecker | None) -> None:
        self._conflictChecker = checker

    def _Text(self, key: str, default: str, **kwargs) -> str:
        return T(self._strings, key, default, **kwargs)

    def _IconButton(self, glyph: str, tooltip: str) -> QPushButton:
        button = QPushButton(glyph)
        button.setStyleSheet(ICON_BUTTON_STYLE)
        button.setFixedWidth(ICON_BUTTON_WIDTH)
        button.setToolTip(tooltip)
        return button

    def _PrefixSource(self) -> str:
        return self.edit.value() or self._default

    def _RefreshButtons(self) -> None:
        value = self.edit.value()
        self.clearButton.setEnabled(bool(value))
        self.resetButton.setEnabled(value != self._default)
        parsed = Hotkeys.Parse(self._default)
        shownDefault = parsed.Display() if parsed is not None else self._default
        self.resetButton.setToolTip(
            self._Text("hotkey.reset", "Restore default ({value})", value=shownDefault or "-")
        )

    def _AcceptCandidate(self, value: str) -> bool:
        conflict = self._conflictChecker(value) if self._conflictChecker is not None else ""
        if conflict:
            self._Warn(self._Text("hotkey.conflict", "Already used by {name}. Pick another one.", name=conflict))
            return False
        self._Warn("")
        return True

    def _ShowInvalid(self, hotkey: Hotkeys.Hotkey | None) -> None:
        if self._gameKey:
            self._Warn(self._Text("hotkey.invalid_game_key", "That key cannot be used here. Try another one."))
            return
        if hotkey is not None and Hotkeys.IsLoneModifier(hotkey):
            self._Warn(self._Text("hotkey.lone_modifier", "Ctrl, Alt, Shift and Win only work together with another key."))
            return
        self._Warn(self._Text("hotkey.invalid", "That combination is not supported. Try another one."))

    def _Warn(self, message: str) -> None:
        self.warning.ShowMessage(message)

    def _Captured(self, value: str) -> None:
        self._RefreshButtons()
        self.valueChanged.emit(value)

    def _Clear(self) -> None:
        self._Warn("")
        self._Apply("")

    def _Reset(self) -> None:
        if self._AcceptCandidate(self._default):
            self._Apply(self._default)

    def _Apply(self, value: str) -> None:
        self.edit.SetValue(value)
        self._RefreshButtons()
        self.valueChanged.emit(value)
