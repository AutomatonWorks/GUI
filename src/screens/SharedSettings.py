"""Settings rows every game has, matching the keys in automaton_gui/shared_keys.py.
Each game's GameConf.py splices them into its General and Keybinds editors."""

from __future__ import annotations

from automaton_gui.I18n import T
from automaton_gui.Inischema import IniFile
from automaton_gui.screens.SettingsSchema import (
    BoolSetting,
    FileSetting,
    GameKeySetting,
    GridSection,
    HotkeySetting,
    LabeledSection,
    NumberSetting,
    Section,
    Setting,
    SettingTab,
    Tab,
    ToggledHotkeySetting,
)

LOG_LEVELS = ["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "FATAL"]


def XxmiSettings(strings: dict | None = None) -> list[Setting]:
    return [
        FileSetting(
            "xxmi_exe",
            T(strings, "general_settings.xxmi_exe.label", "XXMI Launcher executable (optional)"),
            filter="Executable (*.exe)",
            help=T(
                strings,
                "general_settings.xxmi_exe.help",
                "When set, the game is launched through XXMI (mods injected) instead "
                "of the vanilla exe.",
            ),
        ),
        BoolSetting(
            "xxmi_enabled",
            T(strings, "general_settings.xxmi_enabled.label", "Launch with mods"),
            shownBy="xxmi_exe",
            help=T(
                strings,
                "general_settings.xxmi_enabled.help",
                "Untick to launch the vanilla game even though an XXMI executable is set.",
            ),
        ),
    ]


def OverlaySettings(conf: IniFile, strings: dict | None = None) -> list[Setting]:
    return [
        BoolSetting(
            "overlay_enabled",
            T(strings, "general_settings.overlay_enabled.label", "Show status overlay"),
            default=conf.Default("General", "overlay_enabled"),
            help=T(strings, "general_settings.overlay_enabled.help", "Show the status strip over the game window."),
        ),
    ]


def MacrosTab(strings: dict | None, *sections: Section) -> SettingTab:
    return Tab(T(strings, "keybinds.tab_macros", "Macros"), *sections)


def GameKeysTab(strings: dict | None, *sections: Section, columns: int | None = None) -> SettingTab:
    return Tab(T(strings, "keybinds.tab_game", "Game"), *sections, columns=columns)


def AutomatonControlsTab(conf: IniFile, strings: dict | None = None, assists: tuple[Setting, ...] = ()) -> SettingTab:
    """Keys that drive the automaton itself, the same in every game; `assists` adds the game's own hold-to rows."""
    def Hk(key: str, labelKey: str, labelDefault: str, helpDefault: str = "") -> Setting:
        return HotkeySetting(
            key,
            T(strings, f"keybinds.{labelKey}", labelDefault),
            default=conf.Default("HotkeySettings", key),
            help=T(strings, f"keybinds.{labelKey}_help", helpDefault) if helpDefault else "",
        )

    return Tab(
        T(strings, "keybinds.tab_controls", "Automaton controls"),
        LabeledSection(
            "HotkeySettings",
            T(strings, "keybinds.section_automaton", "Hotkeys - Automaton"),
            Hk("MacroMenuHK", "macro_menu", "Macro menu"),
            Hk("PauseHK", "suspend_script", "Suspend script"),
            Hk("ReloadHK", "reload_script", "Reload script"),
            Hk("ExitHK", "kill_script", "Kill script"),
            Hk("BossKeyHK", "boss_key", "Boss key (minimize game and kill macro)"),
            Hk("MuteGameHK", "mute_game", "Mute game", "Mutes or unmutes the game in the Windows volume mixer. The status bar shows a green speaker or a red crossed one."),
            Hk("OverlayHK", "toggle_overlay", "Toggle status overlay"),
            Hk("OverlayHideHK", "hide_overlay", "Hide status overlay completely"),
            Hk("DarkenScreenHK", "darken_screen", "Darken screen", "Covers the game's monitor in black, showing only the running macro, its step and the key to undo it. Macros keep running."),
        ),
        LabeledSection(
            "HotkeySettings",
            T(strings, "keybinds.section_assists", "Hotkeys - Assists"),
            *HoldClickSettings(conf, strings),
            *ContextActionSettings(conf, strings),
            *assists,
        ),
    )


def HoldClickSettings(conf: IniFile, strings: dict | None = None) -> list[Setting]:
    return ToggledHotkeySetting(
        "HoldClickHK",
        T(strings, "keybinds.hold_click", "Hold for auto click"),
        "HoldClickEnabled",
        default=conf.Default("HotkeySettings", "HoldClickHK"),
        toggleDefault=conf.Default("HotkeySettings", "HoldClickEnabled"),
        help=T(
            strings,
            "keybinds.hold_click_help",
            "While the key is held, left click is spammed (handy to skip dialogues). "
            "Untick to leave the key alone.",
        ),
    )


def ContextActionSettings(conf: IniFile, strings: dict | None = None) -> list[Setting]:
    toggleRow = HotkeySetting(
        "ContextActionToggleHK",
        T(strings, "keybinds.context_action_toggle", "Contextual action on/off"),
        default=conf.Default("HotkeySettings", "ContextActionToggleHK"),
        help=T(
            strings,
            "keybinds.context_action_toggle_help",
            "Switches the contextual action on and off while playing. The status bar shows which.",
        ),
    )
    return [*ToggledHotkeySetting(
        "ContextActionHK",
        T(strings, "keybinds.context_action", "Contextual action"),
        "ContextActionEnabled",
        default=conf.Default("HotkeySettings", "ContextActionHK"),
        toggleDefault=conf.Default("HotkeySettings", "ContextActionEnabled"),
        help=T(
            strings,
            "keybinds.context_action_help",
            "Does a different thing in the world and in menus (for example going back). "
            "Untick to leave the key alone.",
        ),
    ), toggleRow]


def ModsToggleKeySetting(conf: IniFile, strings: dict | None = None, conflictGroup: str = "") -> Setting:
    return GameKeySetting(
        "mods_toggle_key",
        T(strings, "keybinds.mods_toggle", "Mods toggle (XXMI)"),
        default=conf.Default("GameKeySettings", "mods_toggle_key"),
        allowModifiers=True,
        conflictGroup=conflictGroup,
        help=T(
            strings,
            "keybinds.mods_toggle_help",
            "Key that switches the XXMI mods on and off. It is written into the importer's key "
            "bindings when the game launches through XXMI. Pick one the game does not use.",
        ),
    )


def AccountSwitcherSection(conf: IniFile, strings: dict | None = None) -> LabeledSection:
    def Kt(key: str, default: str) -> str:
        return T(strings, f"keybinds.{key}", default)

    return LabeledSection(
        "HotkeySettings",
        Kt("section_account_switcher", "Hotkeys - Account switcher"),
        *[
            HotkeySetting(f"Account{n}HK", Kt(f"account_{n}", f"Account {n}"), default=conf.Default("HotkeySettings", f"Account{n}HK"))
            for n in range(10)
        ],
    )


def DevToggleSection(conf: IniFile, strings: dict | None = None) -> LabeledSection:
    return LabeledSection(
        "Dev",
        "",
        BoolSetting(
            "Dev",
            T(strings, "general_settings.dev.label", "Dev mode"),
            default=conf.Default("Dev", "Dev"),
            help=T(
                strings,
                "general_settings.dev.help",
                "Adds a Dev settings window under Configuration, opens the console and enables its keys.",
            ),
        ),
    )


# The Dev editor's grid, a row of (factory, key, i18n id, label, help, options) cells each. The label
# and help come from dev.<id> and dev.<id>_help; every default is the conf schema's.
DEV_ROWS = (
    (
        (HotkeySetting, "ShowPixelHK", "show_pixel", "Show pixel",
         "Print the color and coordinates under the cursor to the console.", {}),
        (BoolSetting, "console_enabled", "console_enabled", "Show console",
         "Open the log console. Only while Dev mode is on.", {}),
    ),
    (
        (HotkeySetting, "TestFunctionHK", "test_function", "Test function",
         "Call TestFunction() for quick iteration.", {}),
        (NumberSetting, "console_left_gap", "console_left_gap", "Console left gap",
         "Left margin (pixels) of the console window.", {"min": 0, "max": 10000}),
    ),
    (
        (HotkeySetting, "KeyRecorderHK", "key_recorder", "Key recorder",
         "Press once to start recording keys and camera, again to stop and copy the script to the clipboard. "
         "Source runs only.", {}),
        (NumberSetting, "console_colums", "console_colums", "Console columns",
         "Width of the console window in columns.", {"min": 20, "max": 1000}),
    ),
    (
        (BoolSetting, "ignore_locks", "ignore_locks", "Ignore locks",
         "Treat every lock as unlocked, handy to test without waiting.", {}),
        (BoolSetting, "perf_metrics", "perf_metrics", "Performance metrics",
         "Log how long the startup, the tray menu and the launch menu take. Only while Dev mode is on.", {}),
    ),
    (
        (BoolSetting, "compile_skip_prompt", "compile_skip_prompt", "Skip build prompt",
         "Skip the dialog AppCompiler shows after a successful build.", {}),
        (BoolSetting, "full_reload", "full_reload", "Full reload",
         "Reload restarts the whole app, so code changes are picked up. Off, it only stops every macro.", {}),
    ),
    (
        (HotkeySetting, "CaptureOverlayHK", "capture_overlay_hk", "Toggle capture overlay",
         "Switches Capture overlay on and off. The status bar shows a green eye while pixel and OCR reads see "
         "through the overlay, a red crossed one while they hit it.", {}),
        (BoolSetting, "capture_overlay", "capture_overlay", "Capture overlay",
         "Let screenshots and screen recordings capture the status overlay and the key hints. Pixel and OCR "
         "reads can then see them.", {}),
    ),
)
# only offered when the game's conf schema has the key
DEV_BETA_ROW = (
    (BoolSetting, "beta_test_mode", "beta_test_mode", "Beta test mode",
     "Add colour tolerance to every pixel search, for beta clients that dither the UI.", {}),
)


def DevSection(conf: IniFile, strings: dict | None = None, extraRows: tuple = ()) -> Section:
    def Cell(factory, key: str, textId: str, label: str, helpText: str, options: dict) -> Setting:
        return factory(
            key,
            T(strings, f"dev.{textId}", label),
            default=conf.Default("Dev", key),
            help=T(strings, f"dev.{textId}_help", helpText),
            **options,
        )

    rows = list(DEV_ROWS)
    if any(k.name == "beta_test_mode" for sec in conf.sections if sec.name == "Dev" for k in sec.keys):
        rows.append(DEV_BETA_ROW)
    rows.extend(extraRows)
    return GridSection("Dev", "", *[[Cell(*spec) for spec in row] for row in rows])
