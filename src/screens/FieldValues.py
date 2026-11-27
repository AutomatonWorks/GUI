from __future__ import annotations

from PySide6.QtCore import QDate, QDateTime
from PySide6.QtWidgets import QComboBox

from automaton_gui import Secrets
from automaton_gui.screens.SettingsSchema import Setting, SettingType, NormalizeChoices


class FieldValues:
    """Puts a loaded value into each Setting's control and reads it back, shared by IniEditor and
    AccountManagerGUI. Needs the screen's `settings`, `_controls`, `_raw` and `_baseline`, plus
    `_RefreshSaveEnabled` (FieldRules)."""

    def _LoadValue(self, name: str, s: Setting, val: object) -> None:
        ctl = self._controls[name]
        if s.type == SettingType.BOOL:
            ctl.setChecked(str(val).strip() == "1")
        elif s.type == SettingType.NUMBER:
            ctl.setValue(int(val) if str(val).strip().lstrip("-").isdigit() else 0)
        elif s.type == SettingType.CHOICE:
            self._raw[name] = val
            self._ChooseValue(ctl, s, val)
        elif s.type == SettingType.INFO:
            ctl.setText(str(val))
            if str(val):
                ctl.setToolTip(str(val))
        elif s.type in (SettingType.HOTKEY, SettingType.GAME_KEY):
            ctl.SetValue(str(val))
        elif s.type == SettingType.DATE:
            ctl.setDate(self._ParseDate(val))
        elif s.type == SettingType.DATERANGE:
            parts = str(val).split("-")
            ctl.setDate(self._ParseDate(parts[0] if parts else ""))
            self._controls[f"{name}.end"].setDate(self._ParseDate(parts[1] if len(parts) >= 2 else ""))
        elif s.type == SettingType.DATETIME:
            ctl.setDateTime(self._ParseUnixTime(val))
        elif s.type == SettingType.PASSWORD:
            ctl.setText(Secrets.Reveal(str(val)))
        else:
            ctl.setText(str(val))

    def _ChooseValue(self, combo: QComboBox, s: Setting, val: object) -> None:
        # a value matching no option leaves the select empty (placeholder shown)
        # rather than misrepresenting it as the first option
        for index, v in enumerate(s.values):
            if str(v) == str(val):
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(-1)

    @staticmethod
    def _ParseDate(val: object) -> QDate:
        text = str(val).strip()
        if len(text) == 8 and text.isdigit():
            date = QDate.fromString(text, "yyyyMMdd")
            if date.isValid():
                return date
        return QDate.currentDate()

    @staticmethod
    def _ParseUnixTime(val: object) -> QDateTime:
        text = str(val).strip()
        if text.isdigit():
            return QDateTime.fromSecsSinceEpoch(int(text))
        return QDateTime.currentDateTime()

    # ---- dependent dropdowns ----
    def SetChoices(self, name: str, choices: list) -> None:
        s = self.settings[name]
        NormalizeChoices(s, choices)
        combo = self._controls[name]
        combo.blockSignals(True)
        combo.clear()
        for value, label in zip(s.values, s.labels):
            combo.addItem(label, value)
        combo.setCurrentIndex(0 if s.values else -1)
        combo.blockSignals(False)
        self._RefreshSaveEnabled()

    # ---- values: resolve / dirty ----
    def ValueOf(self, name: str) -> object:
        s = self.settings[name]
        ctl = self._controls[name]
        if s.type == SettingType.BOOL:
            return 1 if ctl.isChecked() else 0
        if s.type == SettingType.CHOICE:
            # an untouched select whose loaded value matches no option keeps that value
            return ctl.currentData() if ctl.currentIndex() >= 0 else self._raw.get(name, s.default)
        if s.type in (SettingType.NUMBER, SettingType.HOTKEY, SettingType.GAME_KEY):
            return ctl.value()
        if s.type == SettingType.DATE:
            return ctl.date().toString("yyyyMMdd")
        if s.type == SettingType.DATERANGE:
            end = self._controls[f"{name}.end"]
            return ctl.date().toString("yyyyMMdd") + "-" + end.date().toString("yyyyMMdd")
        if s.type == SettingType.DATETIME:
            return ctl.dateTime().toSecsSinceEpoch()
        return ctl.text()

    def _Snapshot(self) -> dict[str, str]:
        return {
            name: str(self.ValueOf(name))
            for name, s in self.settings.items()
            if s.type != SettingType.INFO
        }

    def IsDirty(self) -> bool:
        return any(str(self.ValueOf(name)) != val for name, val in self._baseline.items())

    def _ChangedValues(self) -> dict[str, object]:
        """The savable settings whose value differs from what was loaded, so a save never
        rewrites a key it did not change (another writer may have changed it meanwhile)."""
        changed: dict[str, object] = {}
        for name, s in self.settings.items():
            if s.type == SettingType.INFO or s.transient:
                continue
            value = self.ValueOf(name)
            if str(value) != self._baseline[name]:
                # the field holds the plain password; only the encrypted one is ever stored
                if s.type == SettingType.PASSWORD:
                    value = Secrets.Protect(str(value))
                changed[name] = value
        return changed

    # ---- required gating ----
    # the "Section.key" of every required choice left unpicked
    def _MissingRequired(self) -> list[str]:
        return [
            name
            for name, s in self.settings.items()
            if s.type == SettingType.CHOICE and s.required and self._controls[name].currentIndex() < 0
        ]

    def _RequiredProblems(self) -> dict[str, str]:
        message = self.T("ini_editor.required", "Required field")
        return {name: message for name in self._MissingRequired()}
