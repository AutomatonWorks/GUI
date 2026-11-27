"""The General settings window: its three tabs and the rows every game shares.
Each game's GameConf.general_schema() calls GeneralTabs() and slots its own rows in."""

from __future__ import annotations

from automaton_gui.Displays import ListDisplays
from automaton_gui.I18n import T
from automaton_gui.Inischema import IniFile
from automaton_gui.screens.SettingsSchema import (
    BoolSetting,
    ChoiceSetting,
    FileSetting,
    LabeledSection,
    Section,
    Setting,
    SettingTab,
    Tab,
)
from automaton_gui.screens.SharedSettings import LOG_LEVELS, DevToggleSection, OverlaySettings

# Same list as SupportedResolutions in screen/LibScreen.ahk2
LAUNCH_RESOLUTIONS = [
    ("FHD", 1920, 1080),
    ("UW-FHD", 2560, 1080),
    ("QHD", 2560, 1440),
    ("UW-QHD", 3440, 1440),
    ("WUXGA", 1920, 1200),
]


def GeneralTabs(
    conf: IniFile,
    strings: dict | None,
    *,
    gameExeHelp: str,
    languages: list,
    languageDefault: object,
    launchModes: list,
    accountChoices: list | None,
    activeAccountHelp: str,
    languageHelp: str = "Language for detection strings and labels.",
    launchExtras: tuple | list = (),
    automatonSections: tuple | list = (),
) -> list[SettingTab]:
    """Game & launch / Automaton / Advanced. launchExtras go after the game executable,
    automatonSections (the game's own [Section]s) under the Automaton rows."""
    def Gt(key: str, default: str) -> str:
        return T(strings, f"general_settings.{key}", default)

    return [
        Tab(
            Gt("tab_launch", "Game & launch"),
            LaunchSection(conf, strings, gameExeHelp, launchExtras),
        ),
        Tab(
            Gt("tab_automaton", "Automaton"),
            AutomatonSection(conf, strings, languages, languageDefault, languageHelp, launchModes, accountChoices, activeAccountHelp),
            *automatonSections,
        ),
        Tab(
            Gt("tab_advanced", "Advanced"),
            LabeledSection(
                "General",
                "",
                ChoiceSetting(
                    "log_level",
                    Gt("log_level.label", "Log level"),
                    LOG_LEVELS,
                    default=conf.Default("General", "log_level"),
                    help=Gt("log_level.help", "Minimum severity that gets written to the log."),
                ),
            ),
            DevToggleSection(conf, strings),
        ),
    ]


def LaunchSection(conf: IniFile, strings: dict | None, gameExeHelp: str, launchExtras: tuple | list) -> Section:
    def Gt(key: str, default: str) -> str:
        return T(strings, f"general_settings.{key}", default)

    return LabeledSection(
        "General",
        "",
        FileSetting(
            "game_exe",
            Gt("game_exe.label", "Game executable"),
            filter="Executable (*.exe)",
            help=Gt("game_exe.help", gameExeHelp),
        ),
        *launchExtras,
        *LaunchDisplaySettings(conf, strings),
    )


def AutomatonSection(
    conf: IniFile,
    strings: dict | None,
    languages: list,
    languageDefault: object,
    languageHelp: str,
    launchModes: list,
    accountChoices: list | None,
    activeAccountHelp: str,
) -> Section:
    def Gt(key: str, default: str) -> str:
        return T(strings, f"general_settings.{key}", default)

    return LabeledSection(
        "General",
        "",
        ChoiceSetting(
            "language",
            Gt("language.label", "Language"),
            languages,
            default=languageDefault,
            help=Gt("language.help", languageHelp),
        ),
        ChoiceSetting(
            "launchMode",
            Gt("launch_mode.label", "Launch mode"),
            launchModes,
            default=conf.Default("General", "launchMode"),
            help=Gt("launch_mode.help", "The way the game is launched when the script starts."),
        ),
        ChoiceSetting(
            "activeAccount",
            Gt("active_account.label", "Active account"),
            accountChoices or [("0", "Account0")],
            default=str(conf.Default("General", "activeAccount")),
            help=Gt("active_account.help", activeAccountHelp),
        ),
        BoolSetting(
            "show_report",
            Gt("show_report.label", "Show report after macros"),
            default=conf.Default("General", "show_report"),
            help=Gt("show_report.help", "Show a report at the end of a macro to see what it has done."),
        ),
        *OverlaySettings(conf, strings),
    )


def LaunchDisplaySettings(conf: IniFile, strings: dict | None = None) -> list[Setting]:
    def Gt(key: str, default: str) -> str:
        return T(strings, f"general_settings.{key}", default)

    gameDefault = ("", Gt("launch_default", "Game default"))
    unlockerNote = Gt("launch_unlocker_note", "Not applied when Genshin starts through the FPS Unlocker, which has its own settings.")
    resolutions = [(f"{w}x{h}", f"{name} - {w}x{h}") for name, w, h in LAUNCH_RESOLUTIONS]
    return [
        ChoiceSetting(
            "launch_resolution",
            Gt("launch_resolution.label", "Launch resolution"),
            [gameDefault, *resolutions],
            default=conf.Default("General", "launch_resolution"),
            help=Gt("launch_resolution.help", "Resolution the game starts at.") + "\n" + unlockerNote,
        ),
        ChoiceSetting(
            "launch_display",
            Gt("launch_display.label", "Launch display"),
            [gameDefault, *ListDisplays()],
            default=conf.Default("General", "launch_display"),
            help=Gt("launch_display.help", "Monitor the game starts on.") + "\n" + unlockerNote,
        ),
        BoolSetting(
            "launch_borderless",
            Gt("launch_borderless.label", "Borderless window"),
            default=conf.Default("General", "launch_borderless"),
            help=Gt("launch_borderless.help", "Start the game as a window without borders instead of fullscreen.") + "\n" + unlockerNote,
        ),
    ]
