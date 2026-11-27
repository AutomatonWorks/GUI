from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

from automaton_gui.framework.Anchor import AnchorOverWindow, SetAnchorProvider
from automaton_gui.framework.Assets import AppIcon, SetTaskbarIdentity
from automaton_gui.framework.WheelGuard import InstallWheelGuard
from automaton_gui.ipc import Message, Notify, Reply
from automaton_gui.Payloads import (
    ConfigFromPayload,
    ParseEnergy,
    ParseLaunchOptions,
    ParseMacroSections,
    ParseStageDefaults,
)
from automaton_gui.Perf import PerfTimer, MetricsEnabled

from automaton_gui import Game as game_conf

WINDOW_TITLE = f"{game_conf.APP_NAME} (Python GUI)"

Handler = Callable[[Message, Reply], None]


def BuildApp() -> QApplication:
    SetTaskbarIdentity(f"Automaton.Gui.{WINDOW_TITLE.split(' ')[0]}")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        InstallWheelGuard(app)
    app.setWindowIcon(AppIcon())
    return app


def _IsDone(window: QWidget) -> bool:
    """Closed, and no editor or picker it parents is still open."""
    if window.isVisible():
        return False
    return not any(child.isWindow() and child.isVisible() for child in window.findChildren(QWidget))


class GuiHost:
    """The GUI side of GuiBridge, on the Qt thread. `handle` runs one request:
    a show_* opens its window, whose answer goes back through `reply`.

    It owns no visible window of its own and opens a transient screen on each
    show_* request. `_openWindows` keeps a reference so Python's GC does not
    close a window the moment the handler returns, until it is closed."""

    def __init__(self, app: QApplication, notify: Notify) -> None:
        self._app = app
        self._notify = notify
        self._openWindows: list[QWidget] = []
        self._quitPending = False
        self._trayHost = None
        self._trayActions: dict = {}
        self._retiredTrayHosts: list = []
        # the last stage picker, kept after it closes so the next one can reuse it
        self._stageSelect = None
        self._handlerMap = self._Handlers()

    def Handle(self, message: Message, reply: Reply) -> None:
        self._handlerMap[message.type](message, reply)

    def _Handlers(self) -> dict[str, Handler]:
        openers = {
            "show_launch": self._OpenLaunch,
            "show_macro": self._OpenMacro,
            "show_stage_select": self._OpenStageSelect,
            "show_confirm": self._OpenConfirm,
            "show_alert": self._OpenAlert,
            "show_choice": self._OpenChoice,
            "show_report": self._OpenReport,
            "show_new_team": self._OpenNewTeam,
            "show_setup_wizard": self._OpenSetupWizard,
        }
        handlers = {kind: self._Showing(opener) for kind, opener in openers.items()}
        handlers.update({
            "quit": self._OnQuit,
            "macro_sections": self._OnMacroSections,
            "tray_menu": self._OnTrayMenu,
            "tray_action": self._OnTrayAction,
            "prepare_stage_select": self._OnPrepareStageSelect,
            "close_windows": self._OnCloseWindows,
        })
        return handlers

    def _Showing(self, opener: Callable[[Message, Reply], QWidget]) -> Handler:
        def Handler(message: Message, reply: Reply) -> None:
            self._AnchorOnGame(message.data.get("game_hwnd", 0))
            self._Track(opener(message, reply))

        return Handler

    def _AnchorOnGame(self, gameHwnd: int) -> None:
        # Windows opened later from this one (editors, pickers) center there too.
        if gameHwnd:
            SetAnchorProvider(AnchorOverWindow(lambda: gameHwnd))
        else:
            SetAnchorProvider(None)

    def _Track(self, window: QWidget) -> None:
        stillOpen = []
        for tracked in self._openWindows:
            if not _IsDone(tracked):
                stillOpen.append(tracked)
            elif tracked is not self._stageSelect:
                tracked.deleteLater()
        if window not in stillOpen:
            stillOpen.append(window)
        self._openWindows = stillOpen

    def _NotifyAhk(self, message: Message) -> None:
        self._notify(message)

    def _Config(self, data: dict):
        return ConfigFromPayload(data, self._NotifyAhk)

    @staticmethod
    def _PerfTimer(label: str, data: dict) -> PerfTimer:
        return PerfTimer(label, MetricsEnabled(data.get("config", {}).get("conf_file", "")))

    def _ReportPerf(self, perf: PerfTimer) -> None:
        if perf.enabled:
            self._NotifyAhk(Message(type="perf", data=perf.data()))

    def _OnQuit(self, message: Message, reply: Reply) -> None:
        # AHK does not wait on the report and may exit right after it, so an open report keeps the host alive until dismissed.
        self._quitPending = True
        self._QuitIfPending()

    def _QuitIfPending(self) -> None:
        if self._quitPending and not self._ReportOpen():
            self._app.quit()

    def _ReportOpen(self) -> bool:
        from automaton_gui.screens.Report import ReportGUI

        return any(isinstance(window, ReportGUI) and window.isVisible() for window in self._openWindows)

    def _OpenLaunch(self, message: Message, reply: Reply) -> QWidget:
        # The macro side supplies the real launch options + team presets in the payload
        # (Python stays dumb).
        data = message.data
        perf = self._PerfTimer("show_launch", data)
        from automaton_gui.screens.Launch import OpenLaunchGui

        perf.Lap("import")
        options, teams = ParseLaunchOptions(data)
        perf.Lap("options")
        config = self._Config(data)
        perf.Lap("parse config")
        window = OpenLaunchGui(
            reply,
            options,
            teams,
            currentTeam=data.get("current_team"),
            config=config,
        )
        perf.Lap("build and show window")
        self._ReportPerf(perf)
        return window

    def _OpenMacro(self, message: Message, reply: Reply) -> QWidget:
        # The macro side supplies the macro sections (label + id) in the payload; the
        # chosen id comes back via macro_chosen so AHK runs the action.
        from automaton_gui.screens.Macro import OpenMacroGui

        data = message.data
        return OpenMacroGui(
            reply,
            self._notify,
            ParseMacroSections(data),
            config=self._Config(data),
            title=data.get("title"),
            heading=data.get("heading"),
            showHelp=data.get("help", True),
            which=data.get("which", "macro"),
            showPresetRow=data.get("preset_row", False),
        )

    def _OnMacroSections(self, message: Message, reply: Reply) -> None:
        # The answer to a macro_refresh: the open macro menu redraws only the
        # sections whose buttons changed.
        from automaton_gui.screens.Macro import MacroMenu

        for window in reversed(self._openWindows):
            if isinstance(window, MacroMenu) and window.isVisible():
                window.SetSections(ParseMacroSections(message.data))
                window.SetLocks(message.data.get("config", {}).get("locks", []))
                return

    def _OpenStageSelect(self, message: Message, reply: Reply) -> QWidget:
        # The macro side supplies the stage DB in the payload: the stage types (with their
        # energy numbers), each type's ordered stages (id + name + resolved
        # icon path), and the saved defaults. Python stays dumb - it never reads
        # the AHK stage DB. The pick comes back via stage_confirmed so AHK does
        # the energy math + confirm MsgBox.
        from automaton_gui.screens.StageSelect import (
            OpenStageSelectGui,
            ReuseStageSelectGui,
            StageLayoutKey,
            TeamChoiceFromConfig,
        )

        data = message.data
        perf = self._PerfTimer("show_stage_select", data)
        config = self._Config(data)
        types, stages = config.stageTypes, config.stageStages
        defaults = ParseStageDefaults(data.get("defaults"))
        placeholder = config.placeholder
        energy = ParseEnergy(data.get("energy", {}))
        preset = bool(data.get("preset", 0))
        perf.Lap("parse payload and config")
        cached = self._stageSelect
        key = StageLayoutKey(types, energy, preset, False, TeamChoiceFromConfig(config), config)
        if (cached is not None) and (not cached.isVisible()) and (cached.layoutKey == key):
            window = ReuseStageSelectGui(cached, reply, types, stages, defaults, config, placeholder, energy)
            perf.Lap("reload and show window")
        else:
            window = OpenStageSelectGui(reply, types, stages, defaults, config=config, placeholder=placeholder,
                                           energy=energy, preset=preset)
            perf.Lap("build and show window")
            self._KeepStageSelect(window)
        self._ReportPerf(perf)
        return window

    # Built at startup with the current payload and never shown, so the first picker is a reuse too.
    def _OnPrepareStageSelect(self, message: Message, reply: Reply) -> None:
        from automaton_gui.screens.StageSelect import OpenStageSelectGui

        data = message.data
        perf = self._PerfTimer("prepare_stage_select", data)
        config = self._Config(data)
        window = OpenStageSelectGui(reply, config.stageTypes, config.stageStages,
                                       ParseStageDefaults(data.get("defaults")),
                                       config=config, placeholder=config.placeholder,
                                       energy=ParseEnergy(data.get("energy", {})), preset=bool(data.get("preset", 0)),
                                       show=False)
        perf.Lap("build hidden window")
        self._KeepStageSelect(window)
        self._ReportPerf(perf)

    # The emergency stop: every open window goes, as when the old reload ended the process; a picker
    # a macro was waiting on answers its cancel to nobody.
    def _OnCloseWindows(self, message: Message, reply: Reply) -> None:
        for window in list(self._openWindows):
            if window.isVisible():
                window.close()

    def _KeepStageSelect(self, window: QWidget) -> None:
        previous = self._stageSelect
        self._stageSelect = window
        # a previous one still open stays tracked and goes when it closes
        if (previous is not None) and (previous is not window) and (not previous.isVisible()):
            previous.deleteLater()

    def _OpenConfirm(self, message: Message, reply: Reply) -> QWidget:
        # AHK asks the host to draw the OK/Cancel dialog so it lands on the
        # game's monitor like the rest of the GUI, and the yes/no answer goes
        # back via confirm_result (AHK blocks on it, same as the pickers).
        # `details` carries a summary as FIELDS rather than pre-formatted text -
        # see ConfirmGUI for why the old tab-padded blob had to go.
        from automaton_gui.screens.Confirm import OpenConfirmGui

        data = message.data
        return OpenConfirmGui(
            reply,
            title=data.get("title", "Confirmation"),
            message=data.get("message", ""),
            strings=data.get("strings", {}),
            icon=data.get("icon", ""),
            countdownSeconds=int(data.get("countdown", 0) or 0),
            details=data.get("details") or None,
        )

    def _OpenAlert(self, message: Message, reply: Reply) -> QWidget:
        # A single-OK notice (the AHK one-button MsgBox). Drawn on the game's
        # monitor like every other GUI; AHK blocks until the user dismisses it,
        # which replies alert_result.
        from automaton_gui.screens.Confirm import OpenAlertGui

        data = message.data
        return OpenAlertGui(
            reply,
            title=data.get("title", "Notice"),
            message=data.get("message", ""),
            strings=data.get("strings", {}),
        )

    def _OpenChoice(self, message: Message, reply: Reply) -> QWidget:
        # A question with AHK's own buttons (Retry / Back to menu / Exit...);
        # AHK blocks until choice_result names the picked button id.
        from automaton_gui.screens.Confirm import OpenChoiceGui

        data = message.data
        return OpenChoiceGui(
            reply,
            title=data.get("title", ""),
            message=data.get("message", ""),
            buttons=data.get("buttons", []),
            dismissId=data.get("dismiss", ""),
            strings=data.get("strings", {}),
        )

    def _OpenReport(self, message: Message, reply: Reply) -> QWidget:
        from automaton_gui.screens.Report import OpenReportGui

        # Deferred so the dismissed report has closed before the quit check looks for open ones.
        return OpenReportGui(message.data, lambda: QTimer.singleShot(0, self._QuitIfPending))

    def _OpenNewTeam(self, message: Message, reply: Reply) -> QWidget:
        # Teams the active account was never asked about; AHK stores the answers.
        from automaton_gui.screens.NewTeam import OpenNewTeamGui, ParseNewTeams

        data = message.data
        return OpenNewTeamGui(
            reply,
            ParseNewTeams(data.get("teams", [])),
            account=data.get("account", ""),
            strings=data.get("strings", {}),
        )

    def _OpenSetupWizard(self, message: Message, reply: Reply) -> QWidget:
        # First run: the automaton writes the staged files the wizard hands back at Finish.
        from automaton_gui.screens.wizard.SetupWizard import OpenSetupWizard

        return OpenSetupWizard(reply, message.data, self._Config(message.data))

    def _OnTrayMenu(self, message: Message, reply: Reply) -> None:
        # AHK asks for the tray menu on every right click: a fresh hidden window
        # builds the same menu bar the macro window has, so Locks and the like
        # are as current as when that window opens.
        perf = self._PerfTimer("tray_menu", message.data)
        from automaton_gui.screens.TrayMenu import TrayMenuHost

        perf.Lap("import")
        config = self._Config(message.data)
        perf.Lap("parse config")
        self._RetireTrayHost()
        perf.Lap("retire previous")
        host = TrayMenuHost(config)
        perf.Lap("build host")
        items, self._trayActions = host.Serialize()
        perf.Lap("serialize")
        self._trayHost = host
        reply("tray_menu", {"items": items})
        self._ReportPerf(perf)

    def _RetireTrayHost(self) -> None:
        # A previous host that still has an editor open stays alive, the editor
        # is its child.
        if self._trayHost is not None:
            self._retiredTrayHosts.append(self._trayHost)
        stillOpen = []
        for retired in self._retiredTrayHosts:
            if retired.HasOpenEditors():
                stillOpen.append(retired)
            else:
                retired.deleteLater()
        self._retiredTrayHosts = stillOpen

    def _OnTrayAction(self, message: Message, reply: Reply) -> None:
        action = self._trayActions.get(message.data.get("id"))
        if action is not None:
            # Returning first lets the tray click finish before the action runs.
            QTimer.singleShot(0, action.trigger)

