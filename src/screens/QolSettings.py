"""The QoL buttons tab: keys the automaton answers on game menus ([QoLKeys], see shared_keys.qol_keys).
A game adds its own rows with QolKeySetting in extra sections."""

from __future__ import annotations

from automaton_gui.I18n import T
from automaton_gui.Inischema import IniFile
from automaton_gui.screens.SettingsSchema import GameKeySetting, GridSection, Section, Setting, SettingTab, Tab

QOL_SECTION = "QoLKeys"
# the menu keys may match the game's own keys: they are pressed on different screens
QOL_CONFLICT_GROUP = "qol"


def QolKeySetting(conf: IniFile, strings: dict | None, key: str, labelDefault: str, helpDefault: str = "") -> Setting:
    return GameKeySetting(
        key,
        T(strings, f"keybinds.{key}", labelDefault),
        default=conf.Default(QOL_SECTION, key),
        help=T(strings, f"keybinds.{key}_help", helpDefault) if helpDefault else "",
        conflictGroup=QOL_CONFLICT_GROUP,
    )


def QolButtonsTab(conf: IniFile, strings: dict | None = None, *extraSections: Section) -> SettingTab:
    def Qk(key: str, labelDefault: str, helpDefault: str) -> Setting:
        return QolKeySetting(conf, strings, key, labelDefault, helpDefault)

    gridHelp = "Moves the selection in item grids and side menus."
    return Tab(
        T(strings, "keybinds.tab_qol", "QoL buttons"),
        GridSection(
            QOL_SECTION,
            T(strings, "keybinds.section_qol_menus", "Menus"),
            [Qk("qol_up", "Up", gridHelp), Qk("qol_down", "Down", gridHelp)],
            [Qk("qol_left", "Left", gridHelp), Qk("qol_right", "Right", gridHelp)],
            [Qk("qol_previous", "Previous", "Previous character, agent or event."),
             Qk("qol_next", "Next", "Next character, agent or event.")],
            [Qk("qol_decrease", "Decrease", "Lowers the amount on quantity sliders."),
             Qk("qol_increase", "Increase", "Raises the amount on quantity sliders.")],
            [Qk("qol_main_action", "Main action", "The main button of the screen: confirm, enhance, salvage."),
             Qk("qol_second_action", "Second action", "Claim all, salvage, discard or filter, depending on the screen.")],
            [Qk("qol_third_action", "Third action", "Lock, or delete read mail.")],
        ),
        *extraSections,
        columns=1,
    )
