from __future__ import annotations

from typing import Callable

from automaton_gui.screens.SettingsSchema import Setting, SettingType


class FieldRules:
    """Applies the schema's required / disabledBy / shownBy / shownWhen / onChange flags, shared by IniEditor
    and AccountManagerGUI. Needs the screen's `settings`, `_controls`, `_rowWidgets`,
    `_rowVisibility`, `_saveBtn` and `_MissingRequired` (FieldValues)."""

    def _WireRules(self) -> None:
        for name, s in self.settings.items():
            section = name.partition(".")[0]
            if s.shownBy:
                self._WireShownBy(name, section, s)
            if s.shownWhen:
                self._WireShownWhen(name, section, s)
            if s.disabledBy:
                self._WireDisabledBy(name, section, s)
            if s.type == SettingType.CHOICE and (s.onChange is not None or s.required):
                self._controls[name].currentIndexChanged.connect(self._ChoiceHandler(name, section, s))
            elif s.type == SettingType.BOOL and s.onChange is not None:
                box = self._controls[name]
                box.toggled.connect(lambda checked, sec=section, st=s: st.onChange(self, sec, checked))
                # fire once to sync dependents to the loaded state
                s.onChange(self, section, box.isChecked())

    def _WireShownBy(self, name: str, section: str, s: Setting) -> None:
        source = self._controls[f"{section}.{s.shownBy}"]
        setVisible = self._rowVisibility[name]

        def Sync() -> None:
            setVisible(bool(source.text().strip()))

        source.textChanged.connect(Sync)
        Sync()

    def _WireShownWhen(self, name: str, section: str, s: Setting) -> None:
        key, value = s.shownWhen
        source = self._controls[f"{section}.{key}"]
        setVisible = self._rowVisibility[name]

        def Sync() -> None:
            setVisible(str(source.currentData()) == str(value))

        source.currentIndexChanged.connect(Sync)
        Sync()

    def _WireDisabledBy(self, name: str, section: str, s: Setting) -> None:
        switch = self._controls[f"{section}.{s.disabledBy}"]
        targets = self._rowWidgets[name]

        def Apply(checked: bool) -> None:
            for target in targets:
                target.setEnabled(not checked)

        switch.toggled.connect(Apply)
        Apply(switch.isChecked())

    def _ChoiceHandler(self, name: str, section: str, s: Setting) -> Callable[[int], None]:
        combo = self._controls[name]

        def Handler(index: int) -> None:
            if s.onChange is not None:
                s.onChange(self, section, combo.itemData(index) if index >= 0 else "")
            self._RefreshSaveEnabled()

        return Handler

    def _RefreshSaveEnabled(self) -> None:
        self._saveBtn.setEnabled(not self._MissingRequired())
