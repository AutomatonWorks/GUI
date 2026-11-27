from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QPushButton, QWidget

from automaton_gui.framework.Widgets import ElideText
from automaton_gui.Game import PRESET_STAGE_KEY, PRESET_TYPE_KEY
from automaton_gui.screens.IniFile import IniApply, IniRead
from automaton_gui.screens.StageModel import StageDefaults
from automaton_gui.screens.StageSelect import StageSelectGUI
from automaton_gui.screens.StageTeam import StageTeamsConfig, TeamChoiceFor

# The account's preset stage (what the preset launch modes farm), shared by the launch/macro
# window's preset row and the account settings panels: both read it, show it on a button and
# change it through the same StageSelectGUI picker, which saves the pick to the account at once.

BUTTON_TEXT_PADDING = 16


def ReadPresetStage(accountsFile: str | Path, section: str) -> tuple[int, int]:
    typeID = int(IniRead(accountsFile, section, PRESET_TYPE_KEY, "0") or 0)
    stageID = int(IniRead(accountsFile, section, PRESET_STAGE_KEY, "0") or 0)
    return typeID, stageID


def StageName(stageStages: dict, typeID: int, stageID: int, notSet: str) -> str:
    if typeID and stageID:
        for stage in stageStages.get(typeID, []):
            if stage.id == stageID:
                return stage.name
    return notSet


def ShowStageOnButton(button: QPushButton, name: str, maxWidth: int) -> None:
    """The stage name elided to the button's width, with the full name on the tooltip."""
    button.setText(ElideText(button, name, maxWidth - BUTTON_TEXT_PADDING))
    button.setToolTip(name)


def PresetStagePicker(
    accountsFile: str | Path,
    section: str,
    stageTypes: list,
    stageStages: dict,
    placeholder: str,
    onPicked: Callable[[int, int], None],
    pickOnly: bool,
    parent: QWidget | None,
    stageTeams: StageTeamsConfig | None = None,
    defaultTeam: int | None = None,
) -> StageSelectGUI:
    """The picker preselected on the account's preset stage; a confirm writes the pick (and
    the stage's team, when the game has teams) to the account's section and then calls
    `on_picked(typeID, stageID)`. `defaultTeam` overrides the config's launcher team, for
    a launcher whose team dropdown changed but is not saved yet."""
    typeID, stageID = ReadPresetStage(accountsFile, section)
    teamChoice = TeamChoiceFor(stageTeams, accountsFile, section, defaultTeam) if stageTeams else None

    def OnConfirm(pickedType: int, pickedStage: int, *_rest) -> None:
        IniApply(accountsFile, {
            (section, PRESET_TYPE_KEY): pickedType,
            (section, PRESET_STAGE_KEY): pickedStage,
        })
        onPicked(pickedType, pickedStage)

    return StageSelectGUI(
        stageTypes,
        stageStages,
        StageDefaults(typeID, stageID, 0),
        onConfirm=OnConfirm,
        placeholder=placeholder,
        preset=True,
        pickOnly=pickOnly,
        teamChoice=teamChoice,
        parent=parent,
    )
