"""Conf keys every game has, spliced into each game's app/utils/IniGenerator.py.
Their settings rows are in screens/shared_settings.py and their texts in
i18n/LangCommons_en.ahk2, so adding one of these options is an edit in commons only."""

from automaton_gui.Inischema import Key


def XxmiKeys() -> list[Key]:
    return [
        Key("xxmi_exe", "", r"""
            Optional: full path to XXMI Launcher.exe. When set, the game is launched
                      through XXMI (mods injected) instead of the vanilla executable."""),
        Key("xxmi_enabled", 1, "Launch through XXMI when xxmi_exe is set. Value: 1 or 0"),
    ]


def LaunchDisplayKeys() -> list[Key]:
    note = "Not applied when Genshin starts through the FPS Unlocker, which has its own settings."
    return [
        Key("launch_resolution", "", f"Resolution the game starts at, as WIDTHxHEIGHT (e.g. 2560x1440). Empty = the game's own. {note}"),
        Key("launch_display", "", f"Device path of the monitor the game starts on, picked in the settings window. Empty = the game's own. {note}"),
        Key("launch_borderless", 0, f"Start the game as a borderless window. Value: 1 or 0. {note}"),
    ]


def BackupKeys() -> list[Key]:
    return [
        Key("backup_auto", 1, "Write a backup of the settings files on its own, set from the Data menu. Value: 1 or 0"),
        Key("backup_interval_hours", 24, "Hours between automatic backups"),
        Key("backup_keep", 7, "Automatic backups kept: older ones are deleted, manual ones never"),
    ]


# [General]; the first-run setup wizard opens on every start until it is 1
SETUP_DONE_KEY = "setup_done"


def SetupKeys() -> list[Key]:
    return [Key(SETUP_DONE_KEY, 0, "Set when the first-run setup is finished. Value: 1 or 0")]


def OverlayKeys() -> list[Key]:
    return [Key("overlay_enabled", 1, "Show the status overlay. Value: 1 or 0")]


def QoLKeys() -> list[Key]:
    """[QoLKeys]: keys the automaton answers on game menus, drawn as key hints. Read through QoLKey."""
    return [
        Key("qol_up", "w"),
        Key("qol_down", "s"),
        Key("qol_left", "a"),
        Key("qol_right", "d"),
        Key("qol_previous", "q"),
        Key("qol_next", "e"),
        Key("qol_decrease", "1"),
        Key("qol_increase", "3"),
        Key("qol_main_action", "f"),
        Key("qol_second_action", "r"),
        Key("qol_third_action", "t"),
    ]


def OverlayHotkeyKeys() -> list[Key]:
    return [
        Key("OverlayHK", "End"),
        Key("OverlayHideHK", "+F10"),
        Key("DarkenScreenHK", "+F11", "Covers the game's monitor in black, showing only the running macro, its step and the key to undo it."),
        Key("BossKeyHK", ""),
        Key("MuteGameHK", "!m", "Mutes or unmutes the game in the Windows volume mixer."),
    ]


def DevKeys(betaTestMode: bool = False) -> list[Key]:
    keys = [
        Key("Dev", 0),
        Key("ShowPixelHK", "PgDn"),
        Key("TestFunctionHK", "PgUp"),
        Key("KeyRecorderHK", "ScrollLock", "Start and stop recording keys and camera into a paste-ready script. Only while Dev is 1 and running from source."),
        Key("console_enabled", 1),
        Key("console_left_gap", 8),
        Key("console_colums", 144),
        Key("ignore_locks", 0),
        Key("perf_metrics", 0, "Log how long the startup, the tray menu and the launch menu take. Only while Dev is 1. Value: 1 or 0"),
        Key("full_reload", 0, "Reload restarts the whole app, so code changes are picked up. Off, it only stops every macro. Only while Dev is 1. Value: 1 or 0"),
        Key("compile_skip_prompt", 0, "Skip the dialog AppCompiler shows after a successful build. Value: 1 or 0"),
        Key("capture_overlay", 0, "Let screenshots and screen recordings capture the status overlay and the key hints. Only while Dev is 1; pixel and OCR reads can then see them. Value: 1 or 0"),
        Key("CaptureOverlayHK", "!c", "Switches capture_overlay on and off. Only while Dev is 1."),
    ]
    if betaTestMode:
        keys.append(Key("beta_test_mode", 0, "Adds colour tolerance to every pixel search, for beta clients that dither the UI. Only while Dev is 1. Value: 1 or 0"))
    return keys


def ModsToggleKey(default: str = "F6", note: str = "") -> Key:
    comment = "Key that toggles the XXMI mods. Written into the importer's key bindings on launch."
    return Key("mods_toggle_key", default, f"{comment} {note}".strip())


def RemoteKeys() -> list[Key]:
    return [
        Key("remoteLaunch", "", "Set by Ultra-Automaton to start one run, the automaton clears it"),
        Key("remoteMacro", "", "Set by Ultra-Automaton to run one macro, the automaton clears it"),
    ]


def HoldClickKeys() -> list[Key]:
    return [
        Key("HoldClickEnabled", 1, "Hold the HoldClickHK key to spam left click, handy to skip dialogues. Value: 1 or 0"),
        Key("HoldClickHK", "XButton2"),
    ]


def ContextActionKeys() -> list[Key]:
    return [
        Key("ContextActionEnabled", 1, "Let the ContextActionHK key act on the current context (back in menus and so on). Value: 1 or 0"),
        Key("ContextActionHK", "RButton"),
        Key("ContextActionToggleHK", "~Alt & Up", "Switches the ContextActionHK key on and off while the game runs, the status bar shows which. It is on again after a restart."),
    ]
