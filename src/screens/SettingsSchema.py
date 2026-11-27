from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from automaton_gui.screens.ConfigEditor import IniEditor

# IniEditor ported from guis/framework/IniEditor.ahk2: the schema-driven .ini/.conf
# editor every config screen (S10-S12) extends. A project declares its settings
# once as a schema and gets a themed editor window - one row per setting, values
# loaded from the file (schema defaults fill the gaps), written back on Save.
#
#   IniEditor(conf_path, [
#       SettingSection("General",
#           ChoiceSetting("log_level", "Log level", ["DEBUG", "INFO", "WARN"], default="INFO"),
#           ChoiceSetting("end_screen", "End screen", [(0, "Bag"), (1, "Events")], default=0),
#           BoolSetting("ignore_locks", "Ignore daily locks", default=0),
#           NumberSetting("launchMode", "Launch mode", default=0, min=0, max=9999),
#           FileSetting("game_exe", "Game executable", filter="Executable (*.exe)"),
#       ),
#   ], columns=2, title="Edit configuration")
#
# Section names are the literal ini [Section] headers; a big section can be split
# across several SettingSection entries sharing the header (LabeledSection gives
# each part its own on-screen title). Choice options are plain values or
# (value, label) pairs. Every setting accepts help= shown as a tooltip on its
# label. PasswordSetting renders masked with a reveal button.
#
# The fields, and the required / disabledBy / shownBy / onChange rules, come from one
# engine (editor_fields.py, field_values.py, field_rules.py) that IniEditor and
# AccountManagerGUI share, so every flag here works on both screens.
#
# Storage is behind three hooks (ReadValue / WriteValue / CommitFile) so a json
# backend (S11 Events editor) can reuse the whole widget/dirty/validate machinery
# with different IO. The default backend reads/writes a real ini file through
# IniFile (configparser): only the edited keys change; unrelated keys/sections and
# their order survive, comments do not.


class SettingType:
    BOOL = "bool"            # checkbox        -> 1 / 0
    NUMBER = "number"        # spin box        -> clamped to min/max
    CHOICE = "choice"        # dropdown        -> one of `values`
    TEXT = "text"            # free-form edit  -> raw string
    PASSWORD = "password"    # masked edit + reveal toggle -> raw string
    FILE = "file"            # path edit + browse button   -> raw string
    DATE = "date"            # date picker     -> YYYYMMDD
    DATERANGE = "daterange"  # two date pickers -> YYYYMMDD-YYYYMMDD
    DATETIME = "datetime"    # local date + time picker -> Unix seconds
    HOTKEY = "hotkey"        # key-capture field -> AHK hotkey string
    GAME_KEY = "gamekey"     # key-capture field -> the key name the macros send to the game
    INFO = "info"           # read-only full-width text, never saved


# onChange callbacks drive dependent dropdowns; signature: (editor, section, value) -> None.
# `section` is the ini section of the setting that changed, so a screen showing the same
# schema for several sections (the account settings) knows which sibling to update.
OnChange = Callable[["IniEditor", str, object], None]


@dataclass
class Setting:
    type: str
    key: str
    label: str
    default: object = ""
    min: object = None
    max: object = None
    help: str = ""
    filter: str = ""
    required: bool = False
    # transient settings always load their default, are never written, and are
    # read back by the caller (e.g. via on_save) - the AHK transient flag.
    transient: bool = False
    # key of a BOOL setting in the same section; while it is checked this one is greyed out
    disabledBy: str = ""
    # key of a text/file setting in the same section; this row is hidden while that one is empty
    shownBy: str = ""
    # (key, value) of a CHOICE setting in the same section; this row is hidden unless that one holds value
    shownWhen: tuple = ()
    # fixed field width in the account form; 0 = the form's width for the type
    width: int = 0
    # GAME_KEY only: also accept Ctrl / Alt / Shift held with the key
    allowModifiers: bool = False
    # GAME_KEY only: game keys clash with the others of their group only (a menu key may match a battle
    # key); a HOTKEY clashes with every key, since it is pressed while the game is listening too
    conflictGroup: str = ""
    # HOTKEY only: key of a BOOL setting in the same section drawn as a checkbox in front of the field,
    # which greys the field out while unchecked
    toggle: str = ""
    # BOOL only: drawn by the HOTKEY row that names it in `toggle`, so it gets no row of its own
    inline: bool = False
    onChange: OnChange | None = None
    # filled by NormalizeChoices for CHOICE
    values: list = field(default_factory=list)
    labels: list = field(default_factory=list)


@dataclass
class Section:
    section: str  # literal ini [Section] header
    label: str    # on-screen title, "" draws none
    settings: list[Setting]
    # when set, the settings are drawn as these rows of "label field" pairs sharing one grid
    rows: list[list[Setting]] | None = None


@dataclass
class SettingGroup:
    """A titled band of settings laid out as explicit rows.

    Purely visual, unlike Section: every setting still belongs to whatever ini
    section the screen is writing. `rows` is a list of side-by-side settings, so
    a group can put "Column" and "Row" on one line under one "Training target"
    title instead of spelling the prefix out on every label. An empty title
    draws no separator."""
    title: str
    rows: list[list[Setting]]


def Group(title: str, *rows: list[Setting]) -> SettingGroup:
    return SettingGroup(title, [list(r) for r in rows])


def NormalizeChoices(s: Setting, choices: list) -> None:
    s.values = []
    s.labels = []
    for choice in choices:
        if isinstance(choice, (list, tuple)):
            s.values.append(choice[0])
            s.labels.append(str(choice[1]))
        else:
            s.values.append(choice)
            s.labels.append(str(choice))


def SettingSection(section: str, *settings: Setting) -> Section:
    return Section(section, section, list(settings))


def LabeledSection(section: str, label: str, *settings: Setting) -> Section:
    return Section(section, label, list(settings))


def GridSection(section: str, label: str, *rows: list[Setting]) -> Section:
    return Section(section, label, [s for row in rows for s in row], [list(row) for row in rows])


def BoolSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.BOOL, key, label, **o)


def NumberSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.NUMBER, key, label, **o)


def TextSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.TEXT, key, label, **o)


def PasswordSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.PASSWORD, key, label, **o)


def FileSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.FILE, key, label, **o)


def DateSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.DATE, key, label, **o)


def DateRangeSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.DATERANGE, key, label, **o)


def DateTimeSetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.DATETIME, key, label, **o)


def HotkeySetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.HOTKEY, key, label, **o)


def ToggledHotkeySetting(
    key: str, label: str, toggleKey: str, default: object, toggleDefault: object, **o
) -> list[Setting]:
    return [
        BoolSetting(toggleKey, label, default=toggleDefault, inline=True),
        HotkeySetting(key, label, default=default, toggle=toggleKey, **o),
    ]


def GameKeySetting(key: str, label: str, **o) -> Setting:
    return Setting(SettingType.GAME_KEY, key, label, **o)


def InfoSetting(key: str, **o) -> Setting:
    return Setting(SettingType.INFO, key, "", **o)


def ChoiceSetting(key: str, label: str, choices: list, **o) -> Setting:
    s = Setting(SettingType.CHOICE, key, label, **o)
    NormalizeChoices(s, choices)
    return s


@dataclass
class SettingTab:
    """One tab of an IniEditor: its own page of sections, laid out in the editor's columns
    unless `columns` sets this tab's own count (1 stacks every section in one column)."""
    label: str
    sections: list[Section]
    columns: int | None = None


def Tab(label: str, *sections: Section, columns: int | None = None) -> SettingTab:
    return SettingTab(label, list(sections), columns)
