from __future__ import annotations

from pathlib import Path

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from automaton_gui.framework import Hotkeys
from automaton_gui.framework.ErrorBubble import ErrorBubble
from automaton_gui.framework.HotkeyField import HotkeyField
from automaton_gui.framework.Widgets import ApplyFont
from automaton_gui.screens.FieldErrors import HideOnEdit
from automaton_gui.screens.SettingsSchema import Section, Setting, SettingType

# ---- layout constants (edit these to restyle the fields) ----
FORM_HORIZONTAL_SPACING = 16
FORM_VERTICAL_SPACING = 8
INLINE_FIELD_MARGINS = (0, 0, 0, 0)
INLINE_FIELD_SPACING = 6
GRID_HOTKEY_MIN_WIDTH = 180
GRID_NUMBER_MIN_WIDTH = 90
PASSWORD_REVEAL_WIDTH = 64
SECTION_TITLE_FONT_SIZE = 15
SECTION_TOP_GAP_MARGINS = (0, 12, 0, 0)
DATETIME_FORMAT = "yyyy-MM-dd HH:mm"


def SectionTitle(text: str, topGap: bool = False) -> QLabel:
    """The bold title over a group of settings; `topGap` separates it from the group above."""
    label = QLabel(text)
    ApplyFont(label, SECTION_TITLE_FONT_SIZE, bold=True)
    if topGap:
        label.setContentsMargins(*SECTION_TOP_GAP_MARGINS)
    return label


KEY_TYPES = (SettingType.HOTKEY, SettingType.GAME_KEY)


def Clashes(a: Setting, b: Setting) -> bool:
    """Whether two key settings may not share a key (see Setting.conflictGroup)."""
    if (a.type not in KEY_TYPES) or (b.type not in KEY_TYPES):
        return False
    if (a.type == SettingType.HOTKEY) or (b.type == SettingType.HOTKEY):
        return True
    return a.conflictGroup == b.conflictGroup


class SettingFields:
    """The widget for each Setting type, shared by IniEditor and AccountManagerGUI. Needs the
    screen's `settings`, `_controls`, `_errors`, `_rowWidgets`, `_rowVisibility`, `_strings` and `t`;
    every control lands in `_controls` and its error bubble in `_errors`, both under "Section.key"."""

    def _RegisterRow(
        self, name: str, label: QLabel, fieldWidget: QWidget, setVisible: Callable[[bool], None] | None = None
    ) -> None:
        """Remember a setting's label and field so the schema rules can grey out or hide the row."""

        def ShowBoth(visible: bool) -> None:
            label.setVisible(visible)
            fieldWidget.setVisible(visible)

        self._rowWidgets[name] = (label, fieldWidget)
        self._rowVisibility[name] = setVisible or ShowBoth

    def _LabelledField(self, name: str, s: Setting) -> tuple[QLabel, QWidget]:
        """The setting's label and field, both carrying its help as a tooltip."""
        label = QLabel(s.label)
        fieldWidget = self._Field(name, s)
        if s.help:
            label.setToolTip(s.help)
            fieldWidget.setToolTip(s.help)
            # a composite field (password, file) keeps its input apart from the container
            self._controls[name].setToolTip(s.help)
        return label, fieldWidget

    def _Grid(self, sec: Section) -> QWidget:
        block = QWidget()
        grid = QGridLayout(block)
        grid.setContentsMargins(*INLINE_FIELD_MARGINS)
        grid.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        grid.setVerticalSpacing(FORM_VERTICAL_SPACING)
        for r, row in enumerate(sec.rows):
            for c, s in enumerate(row):
                name = f"{sec.section}.{s.key}"
                label, fieldWidget = self._LabelledField(name, s)
                if s.type == SettingType.HOTKEY:
                    fieldWidget.setMinimumWidth(GRID_HOTKEY_MIN_WIDTH)
                elif s.type == SettingType.NUMBER:
                    fieldWidget.setMinimumWidth(GRID_NUMBER_MIN_WIDTH)
                self._RegisterRow(name, label, fieldWidget)
                grid.addWidget(label, r, c * 2)
                grid.addWidget(fieldWidget, r, c * 2 + 1)
        return block

    def _AddRow(self, form: QFormLayout, section: str, s: Setting) -> None:
        name = f"{section}.{s.key}"

        if s.type == SettingType.INFO:
            info = QLabel("")
            info.setWordWrap(True)
            info.setProperty("subtle", True)
            self._controls[name] = info
            form.addRow(info)
            return

        if s.inline:
            return

        fieldWidget = self._Field(name, s)
        # a checkbox carries no text; the form label is the setting label
        label = QLabel(s.label)
        if s.help:
            label.setToolTip(s.help)
        form.addRow(label, fieldWidget)
        self._RegisterRow(name, label, fieldWidget, lambda visible: form.setRowVisible(fieldWidget, visible))

    # the input and its error bubble (FieldErrors)
    def _Field(self, name: str, s: Setting) -> QWidget:
        fieldWidget = self._Input(name, s)
        bubble = ErrorBubble(fieldWidget)
        HideOnEdit(self._controls[name], bubble)
        self._errors[name] = bubble
        return fieldWidget

    def _Input(self, name: str, s: Setting) -> QWidget:
        if s.type == SettingType.BOOL:
            box = QCheckBox()
            self._controls[name] = box
            return box

        if s.type == SettingType.NUMBER:
            spin = QSpinBox()
            spin.setMinimum(int(s.min) if s.min is not None else -2_147_483_648)
            spin.setMaximum(int(s.max) if s.max is not None else 2_147_483_647)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._controls[name] = spin
            return spin

        if s.type == SettingType.CHOICE:
            combo = QComboBox()
            combo.setPlaceholderText(self.T("ini_editor.placeholder", "Select an option"))
            for value, label in zip(s.values, s.labels):
                combo.addItem(label, value)
            self._controls[name] = combo
            return combo

        if s.type == SettingType.PASSWORD:
            return self._PasswordField(name)

        if s.type == SettingType.FILE:
            return self._FileField(name, s)

        if s.type == SettingType.DATE:
            picker = self._DatePicker()
            self._controls[name] = picker
            return picker

        if s.type == SettingType.DATERANGE:
            return self._DaterangeField(name)

        if s.type == SettingType.DATETIME:
            picker = QDateTimeEdit()
            picker.setCalendarPopup(True)
            picker.setDisplayFormat(DATETIME_FORMAT)
            self._controls[name] = picker
            return picker

        if s.type in (SettingType.HOTKEY, SettingType.GAME_KEY):
            if s.toggle:
                return self._ToggledHotkeyField(name, s)
            return self._HotkeyField(name, s)

        edit = QLineEdit()
        self._controls[name] = edit
        return edit

    def _PasswordField(self, name: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(*INLINE_FIELD_MARGINS)
        row.setSpacing(INLINE_FIELD_SPACING)
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        reveal = QPushButton(self.T("common.show", "Show"))
        reveal.setCheckable(True)
        reveal.setFixedWidth(PASSWORD_REVEAL_WIDTH)

        def Toggle(checked: bool) -> None:
            edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            reveal.setText(
                self.T("common.hide", "Hide") if checked else self.T("common.show", "Show")
            )

        reveal.toggled.connect(Toggle)
        row.addWidget(edit, 1)
        row.addWidget(reveal)
        self._controls[name] = edit
        return container

    def _FileField(self, name: str, s: Setting) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(*INLINE_FIELD_MARGINS)
        row.setSpacing(INLINE_FIELD_SPACING)
        edit = QLineEdit()
        browse = QPushButton(self.T("common.browse", "Browse..."))
        browse.clicked.connect(lambda: self._Browse(name, s))
        row.addWidget(edit, 1)
        row.addWidget(browse)
        self._controls[name] = edit
        return container

    def _HotkeyField(self, name: str, s: Setting) -> HotkeyField:
        fieldWidget = HotkeyField(
            self._strings, str(s.default).strip(), s.type == SettingType.GAME_KEY, s.allowModifiers
        )
        fieldWidget.SetConflictChecker(lambda value: self._HotkeyConflict(name, value))
        self._controls[name] = fieldWidget
        return fieldWidget

    def _ToggledHotkeyField(self, name: str, s: Setting) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(*INLINE_FIELD_MARGINS)
        row.setSpacing(INLINE_FIELD_SPACING)
        box = QCheckBox()
        fieldWidget = self._HotkeyField(name, s)
        fieldWidget.setEnabled(box.isChecked())
        box.toggled.connect(fieldWidget.setEnabled)
        row.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(fieldWidget, 1)
        self._controls[f"{name.partition('.')[0]}.{s.toggle}"] = box
        return container

    def _HotkeyConflict(self, name: str, value: str) -> str:
        candidate = Hotkeys.Parse(value)
        for other, setting in self.settings.items():
            if (other == name) or not Clashes(self.settings[name], setting):
                continue
            existing = self._controls[other].value()
            parsed = Hotkeys.Parse(existing)
            if candidate is not None and parsed is not None:
                same = candidate.Identity() == parsed.Identity()
            else:
                same = existing.strip().lower() == value.strip().lower()
            if same and existing.strip():
                return setting.label
        return ""

    def _DatePicker(self) -> QDateEdit:
        picker = QDateEdit()
        picker.setCalendarPopup(True)
        picker.setDisplayFormat("yyyy-MM-dd")
        return picker

    def _DaterangeField(self, name: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(*INLINE_FIELD_MARGINS)
        row.setSpacing(INLINE_FIELD_SPACING)
        start = self._DatePicker()
        end = self._DatePicker()
        row.addWidget(start, 1)
        row.addWidget(QLabel(self.T("common.to", "to")))
        row.addWidget(end, 1)
        self._controls[name] = start
        self._controls[f"{name}.end"] = end
        return container

    def _Browse(self, name: str, s: Setting) -> None:
        from PySide6.QtWidgets import QFileDialog
        from automaton_gui.Version import VersionedTitle

        current = self._controls[name].text().strip()
        start = current if current and Path(current).exists() else ""
        picked, _ = QFileDialog.getOpenFileName(
            self,
            VersionedTitle(self.T("ini_editor.select_file_title", "Select {label}", label=s.label)),
            start,
            s.filter or "",
        )
        if picked:
            self._controls[name].setText(picked)
