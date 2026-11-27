from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from automaton_gui.BackupArchive import BackupError
from automaton_gui.framework.ErrorBubble import ErrorBubble
from automaton_gui.screens.wizard.WizardStep import StepPage, WizardStep

# why a zip cannot be imported, by BackupError.textId; {app} fills other_app
IMPORT_ERRORS = {
    "data.restore.not_a_backup": ("wizard.import.not_a_backup", "This file is not a backup of this automaton."),
    "data.restore.other_app": ("wizard.import.other_app", "This is a backup of {app}, not of this automaton."),
    "data.restore.newer_app": (
        "wizard.import.newer_app", "This backup is from a newer version of the automaton. Update it first."),
}


class WelcomeStep(WizardStep):
    """What the setup is for, and the way to start from a backup instead of from scratch."""

    def Title(self) -> str:
        return self.ctx.T("wizard.welcome.title", "Welcome")

    def Build(self) -> QWidget:
        T = self.ctx.T
        page, column = StepPage(
            T("wizard.welcome.heading", "Welcome"),
            T("wizard.welcome.sub", "A few steps to get the automaton ready: the game, your keys, your accounts "
                                    "and teams. Nothing is saved until Finish."),
        )
        column.addSpacing(16)
        column.addWidget(QLabel(T("wizard.welcome.import_label", "Coming from another install? Load a backup "
                                                                 "and review it step by step.")))
        row = QHBoxLayout()
        button = QPushButton(T("wizard.welcome.import", "Import backup..."))
        button.clicked.connect(self._PickBackup)
        row.addWidget(button)
        row.addStretch(1)
        column.addLayout(row)
        self._loaded = QLabel("")
        self._loaded.setWordWrap(True)
        self._loaded.setProperty("subtle", True)
        column.addWidget(self._loaded)
        self._error = ErrorBubble(button)
        column.addStretch(1)
        self._ShowLoaded()
        return page

    def _PickBackup(self) -> None:
        T = self.ctx.T
        path, _ = QFileDialog.getOpenFileName(
            self.ctx.parent, T("wizard.welcome.import_title", "Import a backup"),
            self.ctx.config.backupsDir, T("data.restore_filter", "Backups (*.zip)"))
        if path:
            self.Import(path)

    def Import(self, path: str) -> None:
        try:
            self.ctx.staging.Import(path)
        except BackupError as problem:
            key, default = IMPORT_ERRORS.get(problem.textId, IMPORT_ERRORS["data.restore.not_a_backup"])
            self._error.ShowMessage(self.ctx.T(key, default, app=problem.detail))
            return
        except OSError as problem:
            self._error.ShowMessage(self.ctx.T("wizard.import.failed", "The backup could not be read: {error}",
                                               error=str(problem)))
            return
        self._error.hide()
        self._ShowLoaded()

    def _ShowLoaded(self) -> None:
        backup = self.ctx.staging.backup
        self._loaded.setText(self.ctx.T("wizard.welcome.loaded", "Loaded {name}. The next steps show its settings.",
                                        name=os.path.basename(backup)) if backup else "")
