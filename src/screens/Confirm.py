from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automaton_gui.ipc import Reply
from automaton_gui import GUIConstants as gc
from automaton_gui.framework.ResultDialog import DIALOG_ROOT_MARGINS, ResultDialog
from automaton_gui.framework.ShellIcon import LoadShellIcon
from automaton_gui.framework.Widgets import HeaderLayout, ApplyFont, DetailHeader, MakeButton

# ---- layout constants (edit these to restyle this screen) ----
ROOT_SPACING = 18
BODY_FONT_SIZE = gc.APP_FONT_POINT_SIZE
BUTTON_ROW_SPACING = gc.SPACING_ROW
ICON_SIZE_PX = 48
ICON_TEXT_SPACING = 16

# ---- details layout (the rich variant, when the caller sends structured rows) ----
# Stacked art is far taller than wide, so fitting it to a SQUARE box lets the
# height cap it and leaves the icons narrow - which is what actually reads as
# their size. Drive it from the width and let the height follow the aspect,
# with a ceiling so a very tall sheet cannot stretch the dialog.
DETAILS_LAYOUT = HeaderLayout(
    artWidth=118,
    artMaxHeight=210,
    spacing=22,
    rowSpacing=6,
    labelMinWidth=120,
    artAlignment=Qt.AlignmentFlag.AlignTop,
    boldValues=False,
)

# ConfirmGUI: the OK/Cancel confirmation the AHK side used to pop with a native
# MsgBox. AHK still builds the summary text (battery math, run breakdown, coffee,
# etc.); this only draws it, so it lands on the game's monitor and foreground like
# the rest of the GUI instead of a stray dialog on whatever monitor was active.
#
# Python stays dumb: title + message arrive in the show_confirm payload; the
# yes/no answer reports out through a callback that OpenConfirmGui maps to the
# `confirm_result {ok}` reply.
#
# Two ways to say the same thing:
#   message  - plain prose (most alerts). Rendered as a wrapped paragraph.
#   details  - {image, heading, subheading, rows[{label,value}], note}. AHK used
#              to pre-format this kind of summary into one blob padded with tabs,
#              which only lined up under a monospace font and still drifted. Now
#              it sends the FIELDS and this lays them out, so the columns are a
#              real layout and the stage's own artwork can sit beside them.


class ConfirmGUI(ResultDialog):
    def __init__(
        self,
        title: str = "Confirmation",
        message: str = "",
        onResult: Callable[[bool], None] | None = None,
        okOnly: bool = False,
        strings: dict | None = None,
        icon: str = "",
        countdownSeconds: int = 0,
        details: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._message = message
        self._details = details or None
        self._onResult = onResult
        self._okOnly = okOnly
        self._icon = icon
        self._countdownSeconds = max(0, int(countdownSeconds))
        self._remaining = self._countdownSeconds
        self._okButton: QPushButton | None = None
        self._okLabel = ""
        self._countdownTimer: QTimer | None = None
        self.title = title or (strings or {}).get(
            "confirm.notice_title" if okOnly else "confirm.default_title",
            "Notice" if okOnly else "Confirmation",
        )
        super().__init__(parent, strings=strings)

    def Build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(*DIALOG_ROOT_MARGINS)
        root.setSpacing(ROOT_SPACING)

        if self._details is not None:
            root.addWidget(DetailHeader(self._details, DETAILS_LAYOUT), 1)
            root.addLayout(self._ButtonRow())
            self.setCentralWidget(central)
            return

        body = QLabel(self._message)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        ApplyFont(body, BODY_FONT_SIZE)

        # Optional native shell icon (shutdown / sleep) to the left of the text.
        pixmap = LoadShellIcon(self._icon, ICON_SIZE_PX) if self._icon else None
        if pixmap is not None and not pixmap.isNull():
            row = QHBoxLayout()
            row.setSpacing(ICON_TEXT_SPACING)
            iconLabel = QLabel()
            iconLabel.setPixmap(pixmap)
            iconLabel.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            row.addWidget(iconLabel, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(body, 1)
            root.addLayout(row, 1)
        else:
            root.addWidget(body, 1)

        root.addLayout(self._ButtonRow())
        self.setCentralWidget(central)

    def _ButtonRow(self) -> QHBoxLayout:
        buttons = QHBoxLayout()
        buttons.setSpacing(BUTTON_ROW_SPACING)
        buttons.addStretch(1)

        # An alert (okOnly) has just an OK button; the confirm has Cancel too.
        if not self._okOnly:
            cancel = MakeButton(self.T("common.cancel", "Cancel"))
            cancel.clicked.connect(self._Reject)
            buttons.addWidget(cancel)

        self._okLabel = self.T("common.ok", "OK")
        ok = MakeButton(self._okLabel, primary=True)
        ok.clicked.connect(self._Accept)
        buttons.addWidget(ok)
        self._okButton = ok
        return buttons

    def OnBuilt(self) -> None:
        super().OnBuilt()
        # A countdown auto-confirms (proceeds with the action) when it hits zero;
        # the ticking value rides on the OK button so it's visibly winding down.
        if self._countdownSeconds > 0:
            self._RenderCountdown()
            timer = QTimer(self)
            timer.setInterval(1000)
            timer.timeout.connect(self._Tick)
            timer.start()
            self._countdownTimer = timer

    def _Tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._Accept()
            return
        self._RenderCountdown()

    def _RenderCountdown(self) -> None:
        if self._okButton is not None:
            self._okButton.setText(f"{self._okLabel} ({self._remaining})")

    # Enter confirms (the primary action), Escape / the window X cancel.
    def OnEnter(self) -> None:
        self._Accept()

    def _Accept(self) -> None:
        self._Resolve(True)

    def _Reject(self) -> None:
        self._Resolve(False)

    def _Resolve(self, ok: bool) -> None:
        self._ResolveWith(lambda: self._Report(ok))

    def _Report(self, ok: bool) -> None:
        if self._onResult is not None:
            self._onResult(ok)

    # The countdown stops however the dialog ends, the window X included.
    def _Settle(self) -> None:
        super()._Settle()
        if self._countdownTimer is not None:
            self._countdownTimer.stop()

    # Dismissing the window (Escape, X) with no button is a Cancel for a confirm,
    # but a plain acknowledge for an alert (there is no "no").
    def _ReportDismissal(self) -> None:
        self._Report(self._okOnly)


class ChoiceGUI(ConfirmGUI):
    """The same dialog with the caller's buttons, each [{id, label, primary}].
    Reports the clicked id; closing the window reports `dismissId`."""

    def __init__(
        self,
        title: str,
        message: str,
        buttons: list[dict],
        dismissId: str,
        onChoice: Callable[[str], None],
        strings: dict | None = None,
    ) -> None:
        self._buttons = buttons
        self._dismissId = dismissId
        self._onChoice = onChoice
        super().__init__(title, message, strings=strings)

    def _ButtonRow(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(BUTTON_ROW_SPACING)
        row.addStretch(1)
        for spec in self._buttons:
            button = MakeButton(str(spec.get("label", "")), primary=bool(spec.get("primary")))
            choiceId = str(spec.get("id", ""))
            button.clicked.connect(lambda _checked=False, cid=choiceId: self.Choose(cid))
            row.addWidget(button)
        return row

    def OnEnter(self) -> None:
        primary = next((b for b in self._buttons if b.get("primary")), None)
        if primary is not None:
            self.Choose(str(primary.get("id", "")))

    def Choose(self, choiceId: str) -> None:
        self._ResolveWith(lambda: self._onChoice(choiceId))

    def _ReportDismissal(self) -> None:
        self._onChoice(self._dismissId)


def OpenChoiceGui(
    reply: Reply,
    title: str,
    message: str,
    buttons: list[dict],
    dismissId: str,
    strings: dict | None = None,
) -> ChoiceGUI:
    """Show a ChoiceGUI and reply `choice_result {choice}` with the picked id."""

    def OnChoice(choiceId: str) -> None:
        reply("choice_result", {"choice": choiceId})

    window = ChoiceGUI(title, message, buttons, dismissId, OnChoice, strings=strings)
    window.ShowCentered()
    return window


def OpenConfirmGui(
    reply: Reply,
    title: str = "Confirmation",
    message: str = "",
    strings: dict | None = None,
    icon: str = "",
    countdownSeconds: int = 0,
    details: dict | None = None,
) -> ConfirmGUI:
    """Show the ConfirmGUI and map its outcome onto the catalog: OK / Cancel both
    reply `confirm_result {ok}` (1 or 0). AHK blocks on this reply, same as the
    show_stage_select / show_macro picks. A countdown auto-replies ok=1 when it
    elapses (the power prompts proceed unless the user cancels)."""

    def OnResult(ok: bool) -> None:
        reply("confirm_result", {"ok": 1 if ok else 0})

    window = ConfirmGUI(
        title,
        message,
        onResult=OnResult,
        strings=strings,
        icon=icon,
        countdownSeconds=countdownSeconds,
        details=details,
    )
    window.ShowCentered()
    return window


def OpenAlertGui(
    reply: Reply,
    title: str = "Notice",
    message: str = "",
    strings: dict | None = None,
) -> ConfirmGUI:
    """Show a single-OK notice (the AHK side used to pop a one-button MsgBox) and
    reply `alert_result {}` once the user dismisses it, so AHK unblocks. Same draw
    path as the confirm dialog, with the Cancel button hidden."""

    def OnResult(_ok: bool) -> None:
        reply("alert_result", {})

    window = ConfirmGUI(title, message, onResult=OnResult, okOnly=True, strings=strings)
    window.ShowCentered()
    return window
