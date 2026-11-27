from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from automaton_gui import GUIConstants as gc
from automaton_gui.framework.Window import GuiApp
from automaton_gui.I18n import T
from automaton_gui.screens.EditorFields import (
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    SectionTitle,
    SettingFields,
)
from automaton_gui.screens.FieldErrors import FieldErrors
from automaton_gui.screens.FieldRules import FieldRules
from automaton_gui.screens.FieldValues import FieldValues
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.SettingsSchema import Section, Setting, SettingTab

# ---- layout constants (edit these to restyle this screen) ----
WINDOW_WIDTH_PER_COLUMN = 600
WINDOW_HEIGHT = 640
CONTENT_MARGINS = (28, 20, 28, 20)
CONTENT_SPACING = 36
COLUMN_SPACING = 8
FOOTER_MARGINS = (28, 12, 28, 16)
FOOTER_SPACING = gc.SPACING_ROW
FIT_SCREEN_FRACTION = 0.9
FIT_FRAME_ALLOWANCE = 4

# The schema (Setting, Section, the *Setting factories, Tab) is in settings_schema.py, the ini
# reader and writer in IniFile.py, the widget per setting type in editor_fields.py, loading and
# reading values in field_values.py and the schema rules in field_rules.py.

class IniEditor(SettingFields, FieldValues, FieldRules, FieldErrors, GuiApp):
    def __init__(
        self,
        file: str | Path,
        sections: list[Section] | list[SettingTab],
        columns: int = 1,
        title: str | None = None,
        validate: Callable[["IniEditor"], dict[str, str]] | None = None,
        strings: dict | None = None,
        onSave: Callable[[], None] | None = None,
        onCancel: Callable[[], None] | None = None,
        width: int | None = None,
        fit: bool = False,
        parent: QWidget | None = None,
        embedded: bool = False,
    ) -> None:
        self.file = str(file)
        self._fit = fit
        self._columns = max(1, columns)
        # tabbed when the schema is a list of Tab(...), else one untitled page
        self._tabbed = bool(sections) and isinstance(sections[0], SettingTab)
        pages = [(tab.label, tab.sections, tab.columns) for tab in sections] if self._tabbed else [("", list(sections), None)]
        self._sections = [sec for _, pageSections, _ in pages for sec in pageSections]
        self._pages = [
            (label, self._Distribute(pageSections, max(1, pageColumns or self._columns)))
            for label, pageSections, pageColumns in pages
        ]
        self._validate = validate
        self._onSave = onSave
        self._onCancel = onCancel
        self._saved = False
        self._pending: dict[tuple[str, str], object] = {}

        # flat lookup: "Section.key" -> Setting, mirroring the AHK settings Map
        self.settings: dict[str, Setting] = {}
        for sec in self._sections:
            for s in sec.settings:
                self.settings[f"{sec.section}.{s.key}"] = s

        self._controls: dict[str, QWidget] = {}
        self._errors: dict[str, QLabel] = {}
        self._rowWidgets: dict[str, tuple[QLabel, QWidget]] = {}
        self._rowVisibility: dict[str, Callable[[bool], None]] = {}
        self._raw: dict[str, object] = {}
        self._baseline: dict[str, str] = {}
        self._saveBtn: QPushButton | None = None

        if title is None:
            title = T(
                strings, "ini_editor.edit_default_title", "Edit {name}", name=Path(self.file).name
            )
        self.title = title
        self.winWidth = width if width is not None else WINDOW_WIDTH_PER_COLUMN * self._columns
        self.winHeight = WINDOW_HEIGHT
        super().__init__(parent, strings=strings, embedded=embedded)

    # no Theme menu (theming is the owner's job); just open the file externally
    def Menu(self) -> None:
        self.AddConfigMenu(
            self.T("menu.file", "&File"),
            [{"name": self.T("common.open_file_externally", "Open file externally"), "path": self.file}],
        )

    # ---- column balancing (longest-processing-time, schema order within column)
    def _SectionWeight(self, sec: Section) -> int:
        return 1 + len(sec.settings)

    def _Distribute(self, sections: list[Section], columns: int) -> list[list[Section]]:
        cols: list[list[tuple[int, Section]]] = [[] for _ in range(columns)]
        heights = [0] * columns
        order = sorted(
            enumerate(sections), key=lambda e: -self._SectionWeight(e[1])
        )
        for index, sec in order:
            target = min(range(columns), key=lambda i: heights[i])
            cols[target].append((index, sec))
            heights[target] += self._SectionWeight(sec)
        return [[sec for _, sec in sorted(col, key=lambda e: e[0])] for col in cols]

    # ---- build ----
    def Build(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._contents: list[QWidget] = []
        self._tabWidget: QTabWidget | None = None
        if self._tabbed:
            self._tabWidget = QTabWidget()
            self._tabWidget.setDocumentMode(True)
            for label, cols in self._pages:
                # && so Qt shows a literal & instead of taking it as a mnemonic
                self._tabWidget.addTab(self._Page(cols), label.replace("&", "&&"))
            outer.addWidget(self._tabWidget, 1)
        else:
            outer.addWidget(self._Page(self._pages[0][1]), 1)
        self._footerWidget = self._Footer()
        # an embedded page is saved by its host (Commit), so its own buttons stay hidden
        self._footerWidget.setVisible(not self.embedded)
        outer.addWidget(self._footerWidget)
        self.setCentralWidget(central)

    def _Page(self, cols: list[list[Section]]) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        columns = QHBoxLayout(content)
        # an embedded single page sits among its host's own fields, so it lines up with them
        flush = self.embedded and not self._tabbed
        columns.setContentsMargins(*((0, 0, 0, 0) if flush else CONTENT_MARGINS))
        columns.setSpacing(CONTENT_SPACING)
        for colSecs in cols:
            columns.addLayout(self._Column(colSecs), 1)
        scroll.setWidget(content)
        self._contents.append(content)
        return scroll

    def _Column(self, colSecs: list[Section]) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(COLUMN_SPACING)
        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        grids: list[QGridLayout] = []
        for i, sec in enumerate(colSecs):
            if sec.label:
                form.addRow(SectionTitle(sec.label, topGap=i > 0))
            if sec.rows is not None:
                block = self._Grid(sec)
                grids.append(block.layout())
                form.addRow(block)
                continue
            for s in sec.settings:
                self._AddRow(form, sec.section, s)
        self._AlignGrids(grids)
        col.addLayout(form)
        col.addStretch(1)
        return col

    @staticmethod
    def _AlignGrids(grids: list[QGridLayout]) -> None:
        """Give stacked grids the same label widths so their columns line up under each other."""
        labelColumns = range(0, max((g.columnCount() for g in grids), default=0), 2)
        for c in labelColumns:
            labels = [g.itemAtPosition(r, c).widget() for g in grids for r in range(g.rowCount())
                      if c < g.columnCount() and g.itemAtPosition(r, c)]
            width = max((label.sizeHint().width() for label in labels), default=0)
            for g in grids:
                g.setColumnMinimumWidth(c, width)

    # ---- values: load ----
    def OnBuilt(self) -> None:
        for sec in self._sections:
            for s in sec.settings:
                name = f"{sec.section}.{s.key}"
                val = s.default if s.transient else self.ReadValue(sec.section, s.key, s.default)
                self._LoadValue(name, s, val)
        self._WireRules()
        self._baseline = self._Snapshot()
        self._RefreshSaveEnabled()
        if self._fit:
            self._FitToContent()

    def _FitToContent(self) -> None:
        for content in self._contents:
            content.layout().activate()
        contentWidth = max(content.sizeHint().width() for content in self._contents)
        contentHeight = max(content.sizeHint().height() for content in self._contents)
        tabBarHeight = self._tabWidget.tabBar().sizeHint().height() if self._tabWidget is not None else 0
        footer = self._footerWidget.sizeHint()
        wantedWidth = max(contentWidth, footer.width()) + FIT_FRAME_ALLOWANCE
        wantedHeight = (
            contentHeight + tabBarHeight + footer.height() + self.menuBar().sizeHint().height() + FIT_FRAME_ALLOWANCE
        )
        available = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(
            min(wantedWidth, int(available.width() * FIT_SCREEN_FRACTION)),
            min(wantedHeight, int(available.height() * FIT_SCREEN_FRACTION)),
        )

    # ---- storage hooks (override for a non-ini backend) ----
    def ReadValue(self, section: str, key: str, fallback: object) -> object:
        return IniRead(self.file, section, key, str(fallback))

    def WriteValue(self, value: object, section: str, key: str) -> None:
        self._pending[(section, key)] = value

    def CommitFile(self) -> None:
        IniApply(self.file, self._pending)

    # ---- save / cancel ----
    def _Footer(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*FOOTER_MARGINS)
        row.setSpacing(FOOTER_SPACING)
        row.addStretch(1)

        self._saveBtn = QPushButton(self.T("ini_editor.save", "Save"))
        self._saveBtn.setProperty("primary", True)
        self._saveBtn.clicked.connect(lambda: self.Save())

        cancel = QPushButton(self.T("ini_editor.cancel", "Cancel"))
        cancel.clicked.connect(self.close)

        row.addWidget(self._saveBtn)
        row.addWidget(cancel)
        return bar

    def Save(self) -> bool:
        if not self.Commit():
            return False
        self._saved = True
        if self._onSave is not None:
            self._onSave()
        self.close()
        return True

    # Writes the changed values without closing; False (with each problem under its field) when they cannot be saved.
    def Commit(self) -> bool:
        self._ClearFieldErrors()
        problems = self._RequiredProblems()
        if self._validate is not None:
            problems.update(self._validate(self))
        if self.ShowFieldErrors(problems):
            return False

        self._pending = {}
        for name, value in self._ChangedValues().items():
            section, key = name.split(".", 1)
            self.WriteValue(value, section, key)
        self.CommitFile()
        self._baseline = self._Snapshot()
        return True

    def OnEnter(self) -> None:
        self.Save()

    # Closing/Cancel with unsaved edits asks first (declining vetoes the close).
    def OnClose(self) -> bool:
        if self._saved:
            return False
        if self.IsDirty() and not self._ConfirmDiscard():
            return True
        if self._onCancel is not None:
            self._onCancel()
        return False

    def _ConfirmDiscard(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            self.T("ini_editor.discard_confirm", "Discard unsaved changes?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
