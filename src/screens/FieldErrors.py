from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

from automaton_gui.framework.ErrorBubble import ErrorBubble

# Validation problems show as a bubble under the field they are about, never in a dialog.


def HideOnEdit(control: QWidget, bubble: ErrorBubble) -> None:
    """Editing the field again clears its error."""
    if isinstance(control, QLineEdit):
        control.textChanged.connect(bubble.hide)
    elif isinstance(control, QComboBox):
        control.currentIndexChanged.connect(bubble.hide)


class FieldErrors:
    """The error bubble of every field, for IniEditor and AccountManagerGUI. Needs the screen's
    `_controls` and `_errors` ("Section.key" -> its ErrorBubble, filled by SettingFields)."""

    # Shows each message under its field and focuses the first; False when there is none.
    def ShowFieldErrors(self, problems: dict[str, str]) -> bool:
        for name, message in problems.items():
            self._errors[name].ShowMessage(message)
        if problems:
            self._controls[next(iter(problems))].setFocus()
        return bool(problems)

    def _ClearFieldErrors(self) -> None:
        for bubble in self._errors.values():
            bubble.hide()
