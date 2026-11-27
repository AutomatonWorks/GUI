from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from automaton_gui.framework.Window import GuiApp

DIALOG_ROOT_MARGINS = (24, 20, 24, 20)
DIALOG_MIN_HEIGHT = 170


class ResultDialog(GuiApp):
    """A dialog AHK blocks on, which reports exactly one outcome: from a button, Enter, or the
    window being closed (Escape, X). Subclasses say what a dismissal reports."""

    winWidth = 540
    winHeight = 320
    themed = True

    def __init__(self, parent: QWidget | None = None, strings: dict | None = None) -> None:
        self._resolved = False
        super().__init__(parent, strings=strings)

    def OnBuilt(self) -> None:
        # Sit above the game so a prompt that proceeds on its own can't be buried.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # These dialogs carry anything from one line to a stage summary, so the
        # height follows the content rather than padding a short notice out to a
        # fixed box. Width stays put so they all look like the same dialog.
        self.setFixedWidth(self.winWidth)
        self.resize(self.winWidth, max(DIALOG_MIN_HEIGHT, self.sizeHint().height()))

    def _ResolveWith(self, report: Callable[[], None]) -> None:
        if self._resolved:
            return
        self._Settle()
        report()
        self.close()

    # Guarded by _resolved so a button-then-close does not double-report.
    def OnClose(self) -> bool:
        if not self._resolved:
            self._Settle()
            self._ReportDismissal()
        return False

    def _Settle(self) -> None:
        """Mark the outcome as reported; overridden to stop whatever was still pending."""
        self._resolved = True

    def _ReportDismissal(self) -> None:
        raise NotImplementedError
