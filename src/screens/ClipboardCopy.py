from __future__ import annotations

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QToolTip

from automaton_gui.I18n import T

LOG_RUN_MARKER = "Welcome to "
TOAST_MS = 2500


def Toast(window, text: str) -> None:
    position = window.mapToGlobal(QPoint(window.width() // 2, window.height() - 60))
    QToolTip.showText(position, text, window, QRect(), TOAST_MS)


def CopyFenced(window, text: str, toastText: str) -> None:
    QApplication.clipboard().setText("```\n" + text + "\n```")
    Toast(window, toastText)


def CopyLastRunLog(window, path: str, strings: dict) -> None:
    if not path:
        return
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    start = 0
    for index in range(len(lines) - 1, -1, -1):
        if LOG_RUN_MARKER in lines[index]:
            start = index
            break
    runLines = lines[start:]
    copied = T(strings, "config_menu.log_copied", "Log copied ({n} lines)", n=len(runLines))
    CopyFenced(window, "\n".join(runLines), copied)
