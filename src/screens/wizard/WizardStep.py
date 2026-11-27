from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.I18n import T
from automaton_gui.screens.wizard.Staging import Staging

# ---- layout constants (edit these to restyle every step) ----
PAGE_MARGINS = (20, 16, 20, 12)
PAGE_SPACING = 4
HEADING_SIZE = 15


@dataclass
class WizardContext:
    """What every step reads: the staged files, the game's data from the payload and the wizard's hooks."""
    staging: Staging
    config: object  # ConfigMenuData
    strings: dict
    modsId: str = ""
    # the wizard re-checks Next whenever a step's completeness may have changed
    onChanged: Callable[[], None] = field(default=lambda: None)
    parent: QWidget | None = None

    def T(self, key: str, default: str, **kwargs) -> str:
        return T(self.strings, key, default, **kwargs)


class WizardStep:
    """One page of the setup wizard. Build makes the page afresh from the staged files every time the
    step is shown; Leave saves it back to them and says whether the wizard may move on."""

    def __init__(self, ctx: WizardContext) -> None:
        self.ctx = ctx

    def Title(self) -> str:
        raise NotImplementedError

    def Build(self) -> QWidget:
        raise NotImplementedError

    def Leave(self) -> bool:
        return True

    # Next stays disabled while a required step is not complete
    def IsComplete(self) -> bool:
        return True


def StepPage(heading: str, subtitle: str, body: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
    """A step's page: its heading, a subtle line under it and the body; the layout takes more widgets."""
    page = QWidget()
    column = QVBoxLayout(page)
    column.setContentsMargins(*PAGE_MARGINS)
    column.setSpacing(PAGE_SPACING)
    title = QLabel(heading)
    ApplyFont(title, HEADING_SIZE, bold=True)
    column.addWidget(title)
    sub = QLabel(subtitle)
    sub.setProperty("subtle", True)
    sub.setWordWrap(True)
    column.addWidget(sub)
    if body is not None:
        column.addWidget(body, 1)
    return page, column

