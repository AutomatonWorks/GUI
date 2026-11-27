from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.ResultDialog import DIALOG_ROOT_MARGINS, ResultDialog
from automaton_gui.framework.Widgets import HeaderLayout, ApplyFont, DetailHeader, MakeButton
from automaton_gui.screens.ClipboardCopy import CopyFenced, CopyLastRunLog

# ---- layout constants (edit these to restyle this screen) ----
ROOT_SPACING = 14
BODY_SPACING = 12
BODY_FONT_SIZE = gc.APP_FONT_POINT_SIZE
BUTTON_ROW_SPACING = gc.SPACING_ROW

HEADER_LAYOUT = HeaderLayout(
    artWidth=96,
    artMaxHeight=150,
    spacing=18,
    rowSpacing=4,
    labelMinWidth=100,
    artAlignment=Qt.AlignmentFlag.AlignVCenter,
    boldValues=True,
)

# ---- items ----
BADGE_WIDTH = 26
ITEM_SPACING = 3
ITEM_BADGE_SPACING = 6
SECTION_TITLE_FONT_SIZE = 10
BADGE_FAMILIES = ["Segoe UI Symbol", "DejaVu Sans", "Arial Unicode MS"]
COLOR_DONE = "#3FA66B"
COLOR_FAILED = "#D9534F"
COLOR_MUTED = "#8A8A8A"

# ---- error console ----
CONSOLE_FONT = "Consolas"
CONSOLE_FONT_SIZE = 8
CONSOLE_HEIGHT = 120

TEXT_VARIANT = "︎"
BADGES = {
    "done": ("✔" + TEXT_VARIANT, COLOR_DONE),
    "locked": ("✔" + TEXT_VARIANT, COLOR_DONE),
    "nothing": ("–", COLOR_MUTED),
    "failed": ("✖" + TEXT_VARIANT, COLOR_FAILED),
    "info": ("•", COLOR_MUTED),
}

# The console is a fixed dark terminal in both themes; it is the only styled box on this screen.
CONSOLE_STYLE = """
QPlainTextEdit#reportConsole {
    background-color: #1E1E1E;
    color: #D4D4D4;
    border: 1px solid rgba(128,128,128,110);
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #264F78;
    selection-color: #FFFFFF;
}
QPlainTextEdit#reportConsole QScrollBar:vertical { background: #1E1E1E; width: 10px; margin: 0; }
QPlainTextEdit#reportConsole QScrollBar:horizontal { background: #1E1E1E; height: 10px; margin: 0; }
QPlainTextEdit#reportConsole QScrollBar::handle { background: #555555; border-radius: 4px; min-width: 24px; min-height: 24px; }
QPlainTextEdit#reportConsole QScrollBar::handle:hover { background: #7A7A7A; }
QPlainTextEdit#reportConsole QScrollBar::add-line, QPlainTextEdit#reportConsole QScrollBar::sub-line { width: 0; height: 0; }
QPlainTextEdit#reportConsole QScrollBar::add-page, QPlainTextEdit#reportConsole QScrollBar::sub-page { background: transparent; }
"""

# ReportGUI: the end-of-macro report. AHK sends FIELDS (never pre-formatted text):
#   title, header {image, heading, subheading, rows[{label,value}]} | null,
#   items[{status, name, detail}], error {summary, text} | null, logFile, strings.
# AHK does not wait for it, so nothing is sent back; on_result only tells the host it was dismissed.


class ReportGUI(ResultDialog):
    def __init__(
        self,
        payload: dict,
        onResult: Callable[[], None] | None = None,
        strings: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._header = payload.get("header") or None
        self._items = payload.get("items") or []
        self._error = payload.get("error") or None
        self._logFile = payload.get("log_file", "")
        self._onResult = onResult
        self.title = payload.get("title") or "Report"
        super().__init__(parent, strings=strings if strings is not None else payload.get("strings"))

    def Build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(*DIALOG_ROOT_MARGINS)
        root.setSpacing(ROOT_SPACING)

        body = QVBoxLayout()
        body.setSpacing(BODY_SPACING)
        if self._header is not None:
            body.addWidget(DetailHeader(self._header, HEADER_LAYOUT))
        if self._items:
            body.addLayout(self._ItemsBlock())
        if self._error is not None:
            body.addLayout(self._ErrorBlock())
        root.addLayout(body)
        root.addStretch(1)
        root.addLayout(self._ButtonRow())
        self.setCentralWidget(central)

    def _ItemsBlock(self) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(ITEM_SPACING)
        for item in self._items:
            block.addLayout(self._ItemLine(item))
        return block

    def _ItemLine(self, item: dict) -> QHBoxLayout:
        status = item.get("status", "info")
        line = QHBoxLayout()
        line.setSpacing(ITEM_BADGE_SPACING)

        glyph, color = BADGES.get(status, BADGES["info"])
        badge = QLabel(glyph)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(BADGE_WIDTH)
        font = QFont()
        font.setFamilies(BADGE_FAMILIES)
        font.setPointSize(BODY_FONT_SIZE)
        font.setBold(True)
        badge.setFont(font)
        badge.setStyleSheet(f"color: {color};")
        line.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        text = QLabel(self._ItemText(item))
        text.setWordWrap(True)
        ApplyFont(text, BODY_FONT_SIZE, bold=status == "failed")
        line.addWidget(text, 1)
        return line

    @staticmethod
    def _ItemText(item: dict) -> str:
        name = str(item.get("name", ""))
        detail = str(item.get("detail", ""))
        return f"{name}: {detail}" if detail else name

    def _ErrorBlock(self) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(6)

        title = QLabel(self.T("report.error_title", "Error"))
        title.setProperty("role", "accent")
        ApplyFont(title, SECTION_TITLE_FONT_SIZE, bold=True)
        block.addWidget(title)

        if self._error.get("summary"):
            summary = QLabel(str(self._error["summary"]))
            summary.setWordWrap(True)
            ApplyFont(summary, BODY_FONT_SIZE, bold=True)
            block.addWidget(summary)

        console = QPlainTextEdit()
        console.setObjectName("reportConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        console.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        console.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont(CONSOLE_FONT, CONSOLE_FONT_SIZE)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        console.setFont(font)
        console.setStyleSheet(CONSOLE_STYLE)
        console.setPlainText(str(self._error.get("text", "")))
        console.setFixedHeight(CONSOLE_HEIGHT)
        block.addWidget(console)
        return block

    def _ButtonRow(self) -> QHBoxLayout:
        buttons = QHBoxLayout()
        buttons.setSpacing(BUTTON_ROW_SPACING)
        buttons.addStretch(1)

        if self._error is not None:
            copyError = MakeButton(self.T("report.copy_error", "Copy error"))
            copyError.clicked.connect(self._CopyError)
            buttons.addWidget(copyError)
            copyLog = MakeButton(self.T("report.copy_session_log", "Copy session log"))
            copyLog.clicked.connect(self._CopySessionLog)
            buttons.addWidget(copyLog)

        ok = MakeButton(self.T("common.ok", "OK"), primary=True)
        ok.clicked.connect(self._Acknowledge)
        buttons.addWidget(ok)
        return buttons

    def _CopyError(self) -> None:
        CopyFenced(
            self,
            str(self._error.get("text", "")),
            self.T("report.error_copied", "Error copied"),
        )

    def _CopySessionLog(self) -> None:
        CopyLastRunLog(self, self._logFile, self._strings)

    def OnEnter(self) -> None:
        self._Acknowledge()

    def _Acknowledge(self) -> None:
        self._ResolveWith(self._ReportDismissal)

    # OK, Enter, Escape and the window X all just acknowledge.
    def _ReportDismissal(self) -> None:
        if self._onResult is not None:
            self._onResult()


def OpenReportGui(payload: dict, onDismiss: Callable[[], None]) -> ReportGUI:
    """Show the end-of-macro report; onDismiss runs once it is dismissed (OK, Enter, Escape or the window X)."""
    window = ReportGUI(payload, onResult=onDismiss, strings=payload.get("strings", {}))
    window.ShowCentered()
    return window
