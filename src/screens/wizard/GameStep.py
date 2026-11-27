from __future__ import annotations

import os

from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from automaton_gui import Game as game_conf
from automaton_gui.framework.ErrorBubble import ErrorBubble
from automaton_gui.screens.ConfigEditor import IniEditor
from automaton_gui.screens.GameExe import ExeProblem
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.SettingsSchema import LabeledSection
from automaton_gui.screens.wizard.WizardStep import StepPage, WizardStep

GENERAL = "General"
GAME_EXE_KEY = "game_exe"
XXMI_EXE_KEY = "xxmi_exe"
XXMI_ENABLED_KEY = "xxmi_enabled"
EXE_FILTER = "Executable (*.exe)"
ITEM_SPACING = 14


class PathField(QWidget):
    """A label with Browse... on its right, the path on its own line under them and a hint below; an error
    floats over the hint.
    The box shows the end of a long path: the file name is the part worth seeing."""

    def __init__(self, label: str, hint: str, browseText: str, onChanged) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        head = QHBoxLayout()
        title = QLabel(label)
        title.setStyleSheet("font-weight: 600;")
        head.addWidget(title)
        head.addStretch(1)
        browse = QPushButton(browseText)
        browse.clicked.connect(self._Browse)
        head.addWidget(browse)
        column.addLayout(head)
        self.edit = QLineEdit()
        self.edit.textChanged.connect(lambda _text: onChanged())
        column.addWidget(self.edit)
        self._hint = QLabel(hint)
        self._hint.setProperty("subtle", True)
        column.addWidget(self._hint)
        self.error = ErrorBubble(self.edit)
        self.edit.textChanged.connect(self.error.hide)
        self._label = label

    def Text(self) -> str:
        return self.edit.text().strip()

    def SetText(self, path: str) -> None:
        self.edit.setText(path)
        self.edit.setCursorPosition(len(path))

    def ShowError(self, message: str) -> None:
        self.error.ShowMessage(message)

    def _Browse(self) -> None:
        current = self.Text()
        start = os.path.dirname(current) if current else ""
        picked, _ = QFileDialog.getOpenFileName(self, self._label, start, EXE_FILTER)
        if picked:
            self.SetText(os.path.normpath(picked))


class GameStep(WizardStep):
    """Where the game is, and the mod launcher it can start through."""

    def Title(self) -> str:
        return self.ctx.T("wizard.game.title", "Game")

    def Build(self) -> QWidget:
        T = self.ctx.T
        page, column = StepPage(T("wizard.game.heading", "Game"),
                                T("wizard.game.sub", "Where the game is installed, and the optional tools it "
                                                     "launches with."))
        column.addSpacing(12)
        browse = T("common.browse", "Browse...")
        self._game = PathField(T("wizard.game.exe", "Game executable"),
                               T("wizard.game.exe_hint", "Required."), browse, self.ctx.onChanged)
        self._game.SetText(self._Read(GAME_EXE_KEY))
        column.addWidget(self._game)
        self._xxmi = None
        if self.ctx.modsId:
            column.addSpacing(ITEM_SPACING)
            self._xxmi = PathField(T("wizard.game.xxmi", "XXMI Launcher (optional)"),
                                   T("wizard.game.xxmi_hint", "Fill if you play with {mods} mods.",
                                     mods=self.ctx.modsId), browse, self._SyncMods)
            self._mods = QCheckBox(T("wizard.game.mods", "Launch with mods"))
            self._mods.setChecked(self._Read(XXMI_ENABLED_KEY, "1") == "1")
            self._xxmi.SetText(self._Read(XXMI_EXE_KEY))
            column.addWidget(self._xxmi)
            column.addWidget(self._mods)
            self._SyncMods()
        column.addSpacing(ITEM_SPACING)
        self._launch = IniEditor(self.ctx.staging.conf,
                                 [LabeledSection(GENERAL, "", *game_conf.LaunchOptions(self.ctx.strings))],
                                 strings=self.ctx.strings, embedded=True)
        column.addWidget(self._launch)
        column.addStretch(1)
        return page

    def IsComplete(self) -> bool:
        return bool(self._game.Text())

    def Leave(self) -> bool:
        strings = self.ctx.strings
        problem = ExeProblem(self._game.Text(), strings, required=True, names=game_conf.GAME_EXE_NAMES)
        self._game.ShowError(problem)
        xxmiProblem = ExeProblem(self._xxmi.Text(), strings, required=False) if self._xxmi else ""
        if self._xxmi is not None:
            self._xxmi.ShowError(xxmiProblem)
        if problem or xxmiProblem:
            return False
        if not self._launch.Commit():
            return False
        updates = {(GENERAL, GAME_EXE_KEY): self._game.Text()}
        if self._xxmi is not None:
            updates[(GENERAL, XXMI_EXE_KEY)] = self._xxmi.Text()
            updates[(GENERAL, XXMI_ENABLED_KEY)] = 1 if self._mods.isChecked() else 0
        IniApply(self.ctx.staging.conf, updates)
        return True

    def _SyncMods(self) -> None:
        self._mods.setVisible(bool(self._xxmi.Text()))

    def _Read(self, key: str, fallback: str = "") -> str:
        return IniRead(self.ctx.staging.conf, GENERAL, key, fallback).strip()
