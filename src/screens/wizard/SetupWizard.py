from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from automaton_gui import Game as game_conf
from automaton_gui.framework.Widgets import MakeButton, Separator
from automaton_gui.framework.Window import GuiApp
from automaton_gui.ipc import Reply
from automaton_gui.screens.wizard.EditorSteps import AccountsStep, KeysStep, TeamsStep
from automaton_gui.screens.wizard.GameStep import GameStep
from automaton_gui.screens.wizard.Staging import Staging
from automaton_gui.screens.wizard.Stepper import Stepper
from automaton_gui.screens.wizard.SummaryStep import SummaryStep
from automaton_gui.screens.wizard.WelcomeStep import WelcomeStep
from automaton_gui.screens.wizard.WizardStep import WizardContext, WizardStep

WIN_WIDTH = 820
WIN_HEIGHT = 700
FOOTER_MARGINS = (12, 9, 12, 9)
FOOTER_SPACING = 8

FINISHED = "setup_finished"
CANCELLED = "setup_cancelled"


class SetupWizard(GuiApp):
    """The first-run setup: one step at a time over copies of the settings files. Finish hands the copies
    (and the imported backup, if any) to the automaton, which writes them; closing ends the automaton."""

    winWidth = WIN_WIDTH
    winHeight = WIN_HEIGHT

    def __init__(self, ctx: WizardContext, onDone, hasTeams: bool) -> None:
        self.ctx = ctx
        self._onDone = onDone
        self._done = False
        self.title = ctx.T("wizard.window_title", "{app} | Setup", app=game_conf.APP_NAME)
        self._steps: list[WizardStep] = [WelcomeStep(ctx), GameStep(ctx), KeysStep(ctx), AccountsStep(ctx)]
        if hasTeams:
            self._steps.append(TeamsStep(ctx))
        self._steps.append(SummaryStep(ctx, self.GoTo, hasTeams))
        self._current = 0
        super().__init__(None, strings=ctx.strings)
        ctx.parent = self
        ctx.onChanged = self._RefreshButtons

    # no menu bar: the setup has nothing to open but its own steps
    def Menu(self) -> None:
        pass

    def Build(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._stepper = Stepper([step.Title() for step in self._steps])
        outer.addWidget(self._stepper)
        outer.addWidget(Separator())
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        outer.addWidget(Separator())
        outer.addWidget(self._Footer())
        self.setCentralWidget(central)

    def OnBuilt(self) -> None:
        self._Show(0)

    def _Footer(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(*FOOTER_MARGINS)
        row.setSpacing(FOOTER_SPACING)
        row.addStretch(1)
        self._backBtn = MakeButton(self.T("wizard.back", "Back"))
        self._backBtn.clicked.connect(self.Back)
        self._nextBtn = MakeButton(self.T("wizard.next", "Next"), primary=True)
        self._nextBtn.clicked.connect(self.Next)
        row.addWidget(self._backBtn)
        row.addWidget(self._nextBtn)
        return bar

    # ---- navigation ----
    def Next(self) -> None:
        if not self._steps[self._current].Leave():
            return
        if self._current == (len(self._steps) - 1):
            self._Finish()
            return
        self._Show(self._current + 1)

    def Back(self) -> None:
        if (self._current > 0) and self._steps[self._current].Leave():
            self._Show(self._current - 1)

    def GoTo(self, stepClass: type) -> None:
        for index, step in enumerate(self._steps):
            if isinstance(step, stepClass):
                self._Show(index)
                return

    def _Show(self, index: int) -> None:
        old = self._stack.currentWidget()
        self._current = index
        page = self._steps[index].Build()
        self._stack.addWidget(page)
        self._stack.setCurrentWidget(page)
        if old is not None:
            self._stack.removeWidget(old)
            old.deleteLater()
        self._stepper.SetCurrent(index)
        self._RefreshButtons()

    def _RefreshButtons(self) -> None:
        last = self._current == (len(self._steps) - 1)
        self._nextBtn.setText(self.T("wizard.finish", "Finish") if last else self.T("wizard.next", "Next"))
        self._nextBtn.setEnabled(self._steps[self._current].IsComplete())
        self._backBtn.setEnabled(self._current > 0)

    # ---- finish / close ----
    def _Finish(self) -> None:
        self._done = True
        staging = self.ctx.staging
        self._onDone(FINISHED, {"conf": staging.conf, "accounts": staging.accounts, "backup": staging.backup})
        self.close()

    def OnClose(self) -> bool:
        if self._done:
            return False
        if not self._ConfirmQuit():
            return True
        self._done = True
        self.ctx.staging.Discard()
        self._onDone(CANCELLED, {})
        return False

    def _ConfirmQuit(self) -> bool:
        answer = QMessageBox.question(
            self, self.windowTitle(),
            self.T("wizard.quit_confirm", "Are you sure you want to quit the setup?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes


def OpenSetupWizard(reply: Reply, data: dict, config) -> SetupWizard:
    """Show the setup wizard; it replies setup_finished {conf, accounts, backup} with the staged files'
    paths, or setup_cancelled when it is closed."""
    files = {"conf": config.confFile, "accounts": data.get("accounts_file", "")}
    staging = Staging(files, game_conf.APP_NAME, game_conf.INI_FILES)
    ctx = WizardContext(staging, config, config.strings, modsId=data.get("mods_id", ""))
    hasTeams = bool(config.stageTeams and config.stageTeams.teams)
    window = SetupWizard(ctx, reply, hasTeams)
    window.ShowCentered()
    return window

