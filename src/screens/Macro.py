from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from automaton_gui import Game as game_conf
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Widgets import ApplyFont, Separator
from automaton_gui.framework.Window import GuiApp
from automaton_gui.I18n import T
from automaton_gui.ipc import Message, Notify, Reply
from automaton_gui.screens.DefaultTeamRow import DefaultTeamRowMixin
from automaton_gui.screens.PresetRow import PresetRowMixin
from automaton_gui.Version import VersionedTitle

# ---- layout constants (edit these to restyle this screen) ----
ROOT_MARGINS = (gc.MARGIN_SCREEN_SIDE, 16, gc.MARGIN_SCREEN_SIDE, 30)
ROOT_SPACING = gc.SPACING_SCREEN
HEADING_FONT_SIZE = 28
SECTION_TITLE_FONT_SIZE = 14
SECTION_GRID_SPACING = 8
MACRO_BUTTON_MIN_HEIGHT = 66
MACRO_BUTTON_FONT_SIZE = 12

HELP_DIALOG_WIDTH = 500
HELP_DIALOG_HEIGHT = 520
HELP_ROOT_MARGINS = (20, 15, 20, 15)
HELP_ROOT_SPACING = 12
HELP_TITLE_FONT_SIZE = 14
HELP_HEADER_FONT_SIZE = gc.APP_FONT_POINT_SIZE

# MacroMenu ported from guis/MacroMenu.ahk2: the macro launcher. Button sections
# built from ONE data table (Sections() in the AHK) - each section is a titled
# grid of macro buttons. Single-click chooses (run=false: AHK confirms first),
# double-click runs straight away (run=true), matching the AHK GuiEvent.CLICK vs
# DOUBLECLICK split where single-click popped a confirm MsgBox and double-click
# ran immediately.
#
# Python stays dumb: the sections arrive as constructor data, and the chosen
# macro reports out through a callback so the IPC glue (OpenMacroGui) maps it
# onto `macro_chosen {id, run}` without the window knowing the channel exists.


@dataclass(frozen=True)
class MacroItem:
    id: str
    label: str


@dataclass(frozen=True)
class MacroSection:
    title: str
    columns: int
    items: list[MacroItem] = field(default_factory=list)
    # buttons per row; empty = `columns` per row
    rows: list[int] = field(default_factory=list)


class MacroButton(QPushButton):
    """A macro button that distinguishes single- from double-click. QPushButton
    fires `clicked` on the first release of a double-click, so a naive wiring
    would emit BOTH the single and the double action. A short timer (the OS
    double-click interval) holds the single-click action; an arriving double
    cancels it - so exactly one of singleClicked / doubleClicked fires."""

    singleClicked = Signal()
    doubleClicked = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(QApplication.doubleClickInterval())
        self._timer.timeout.connect(self.singleClicked.emit)
        self.clicked.connect(self._timer.start)

    def mouseDoubleClickEvent(self, event) -> None:
        super().mouseDoubleClickEvent(event)
        self._timer.stop()
        self.doubleClicked.emit()


class MacroMenu(PresetRowMixin, DefaultTeamRowMixin, GuiApp):
    winWidth = 900
    winHeight = 760

    def __init__(
        self,
        sections: list[MacroSection],
        onChoose: Callable[[str, bool], None] | None = None,
        onCancel: Callable[[], None] | None = None,
        config=None,
        parent: QWidget | None = None,
        title: str | None = None,
        heading: str | None = None,
        showHelp: bool = True,
        showPresetRow: bool = False,
        onRefresh: Callable[[], None] | None = None,
    ) -> None:
        self._sections = list(sections)
        self._onChoose = onChoose
        self._onCancel = onCancel
        self._onRefresh = onRefresh
        self._config = config
        self._picked = False
        self._buttons: list[MacroButton] = []
        self._grids: list[QGridLayout] = []
        self._heading = heading
        self._showHelp = showHelp
        self._showPresetRow = showPresetRow
        strings = config.strings if config else None
        # title/heading overrides let a second, structurally identical menu (e.g.
        # Genshin's Navigation teleport menu) reuse this screen without colliding
        # on the shared "macro.*" strings.
        self.title = title or T(strings, "macro.title", f"{game_conf.APP_NAME} | Macro menu")
        super().__init__(parent, strings=strings)

    # The shared config menu bar (ported from ZzzGui.Menu) lives on this entry
    # window; build it when the host supplied the config data, else just the
    # base Theme menu (the payload-less preview/manual-poke path).
    def Menu(self) -> None:
        if self._config is not None:
            from automaton_gui.screens.ConfigMenu import BuildConfigMenus

            BuildConfigMenus(self, self._config)
        else:
            super().Menu()

    def Build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(*ROOT_MARGINS)
        root.setSpacing(ROOT_SPACING)

        if self._showHelp:
            helpRow = QHBoxLayout()
            helpRow.addStretch(1)
            helpButton = QPushButton(self.T("macro.help_button", "HELP"))
            helpButton.clicked.connect(self._OpenHelp)
            helpRow.addWidget(helpButton)
            root.addLayout(helpRow)

        heading = QLabel(self._heading or self.T("macro.heading", "Macro menu"))
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ApplyFont(heading, HEADING_FONT_SIZE, bold=True)
        root.addWidget(heading)

        root.addWidget(Separator())

        presetRow = self._PresetRow() if self._showPresetRow else None
        teamRow = self._DefaultTeamRow()
        if presetRow is not None or teamRow is not None:
            for row in (presetRow, teamRow):
                if row is not None:
                    centered = QHBoxLayout()
                    centered.addStretch(1)
                    centered.addLayout(row)
                    centered.addStretch(1)
                    root.addLayout(centered)
            root.addWidget(Separator())

        for index, section in enumerate(self._sections):
            root.addWidget(self._SectionTitle(section.title))
            root.addLayout(self._SectionGrid(section))
            if index < len(self._sections) - 1:
                root.addWidget(Separator())

        root.addStretch(1)
        self.setCentralWidget(central)

    def _SectionTitle(self, text: str) -> QLabel:
        label = QLabel(text)
        ApplyFont(label, SECTION_TITLE_FONT_SIZE, bold=True)
        return label

    def _SectionGrid(self, section: MacroSection) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(SECTION_GRID_SPACING)
        self._grids.append(grid)
        self._FillGrid(grid, section)
        return grid

    def _ClearGrid(self, grid: QGridLayout) -> None:
        for col in range(grid.columnCount()):
            grid.setColumnStretch(col, 0)
        while grid.count():
            widget = grid.takeAt(0).widget()
            if widget is not None:
                self._buttons.remove(widget)
                widget.deleteLater()

    def SetLocks(self, locks: list) -> None:
        if self._config is not None:
            self._config.locks = locks

    def SetSections(self, sections: list[MacroSection]) -> None:
        """Rebuild only the sections whose buttons changed, in place."""
        if len(sections) != len(self._sections):
            return
        for index, (grid, old, new) in enumerate(zip(self._grids, self._sections, sections)):
            if old != new:
                self._ClearGrid(grid)
                self._FillGrid(grid, new)
                self._sections[index] = new

    def _FillGrid(self, grid: QGridLayout, section: MacroSection) -> None:
        columns = max(1, section.columns)
        # each row spans the full width: grid cells are the lcm of the row sizes, a button spans its share
        placements = []
        if section.rows:
            columns = math.lcm(*section.rows)
            for row, count in enumerate(section.rows):
                span = columns // count
                for index in range(count):
                    placements.append((row, index * span, span))
        else:
            for slot in range(len(section.items)):
                placements.append((slot // columns, slot % columns, 1))
        for (row, col, span), item in zip(placements, section.items):
            button = MacroButton(item.label)
            button.setMinimumHeight(MACRO_BUTTON_MIN_HEIGHT)
            ApplyFont(button, MACRO_BUTTON_FONT_SIZE)
            button.singleClicked.connect(
                lambda macroId=item.id: self._Pick(macroId, False)
            )
            button.doubleClicked.connect(
                lambda macroId=item.id: self._Pick(macroId, True)
            )
            self._buttons.append(button)
            grid.addWidget(button, row, col, 1, span)
        for col in range(columns):
            grid.setColumnStretch(col, 1)

    def _Pick(self, macroId: str, run: bool) -> None:
        self._picked = True
        if self._onChoose is not None:
            self._onChoose(macroId, run)
        self.close()

    def _RefreshPresetRow(self) -> None:
        super()._RefreshPresetRow()
        self._ReloadDefaultTeam()

    def RequestRefresh(self) -> bool:
        if self._onRefresh is None:
            return False
        self._onRefresh()
        return True

    def _OpenHelp(self) -> None:
        MacroHelpDialog(self, strings=self._strings).exec()

    # Dismissing with no pick (Escape, X) reports a plain close. The AHK window
    # called ExitApp here; in the split architecture Python only reports it.
    def OnClose(self) -> bool:
        if not self._picked and self._onCancel is not None:
            self._onCancel()
        return False


class MacroHelpDialog(QDialog):
    """The HELP page ported from MacroMenu.OpenHelpPage - a static explainer of
    the macro categories."""

    def __init__(self, parent: QWidget | None = None, strings: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(VersionedTitle(T(strings, "macro.help.window_title", "Help")))
        self.resize(HELP_DIALOG_WIDTH, HELP_DIALOG_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(*HELP_ROOT_MARGINS)
        root.setSpacing(HELP_ROOT_SPACING)

        title = QLabel(T(strings, "macro.help.title", f"{game_conf.APP_NAME} - Macro Interface Help"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ApplyFont(title, HELP_TITLE_FONT_SIZE, bold=True)
        root.addWidget(title)

        for paragraph in (
            T(
                strings,
                "macro.help.intro1",
                "The Macro Interface provides interactive button sections for "
                "executing different macro types.",
            ),
            T(
                strings,
                "macro.help.intro2",
                "The layout and behavior of these sections are defined in one data "
                "table, which controls the columns, title and buttons.",
            ),
            T(
                strings,
                "macro.help.intro3",
                "Each macro corresponds to a function in the project - either as a "
                "single action or part of a combined sequence.",
            ),
        ):
            body = QLabel(paragraph)
            body.setWordWrap(True)
            root.addWidget(body)

        header = QLabel(T(strings, "macro.help.category_header", "Category Overview"))
        ApplyFont(header, HELP_HEADER_FONT_SIZE, bold=True)
        root.addWidget(header)

        for line in (
            T(strings, "macro.help.category1", "-  Unique - Standalone macros."),
            T(strings, "macro.help.category2", "-  Combo - Predefined combinations of macros."),
            T(strings, "macro.help.category3", "-  Combat - Used for combat automaton in-game."),
        ):
            root.addWidget(QLabel(line))

        root.addStretch(1)

        footer = QLabel(T(strings, "macro.help.footer", "Press ESC or click the X to close this window."))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setProperty("subtle", True)
        ApplyFont(footer, italic=True)
        root.addWidget(footer)


def OpenMacroGui(
    reply: Reply,
    notify: Notify,
    sections: list[MacroSection],
    config=None,
    title: str | None = None,
    heading: str | None = None,
    showHelp: bool = True,
    which: str = "macro",
    showPresetRow: bool = False,
) -> MacroMenu:
    """Show the MacroMenu and map its outcome onto the WM_COPYDATA catalog: a pick
    replies `macro_chosen {id, run}` (run=true on double-click / run-now), a
    dismissal replies `gui_closed {which}`. `which` (default "macro") lets a
    reused instance - e.g. Genshin's Navigation menu - tag its own dismissal."""

    def OnChoose(macroId: str, run: bool) -> None:
        reply("macro_chosen", {"id": macroId, "run": run})

    def OnCancel() -> None:
        reply("gui_closed", {"which": which})

    def OnRefresh() -> None:
        notify(Message(type="macro_refresh", data={}))

    window = MacroMenu(
        sections,
        onChoose=OnChoose,
        onCancel=OnCancel,
        onRefresh=OnRefresh if which == "macro" else None,
        config=config,
        title=title,
        heading=heading,
        showHelp=showHelp,
        showPresetRow=showPresetRow,
    )
    window.ShowCentered()
    return window
