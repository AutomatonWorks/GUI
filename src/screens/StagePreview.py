from __future__ import annotations

from automaton_gui.Energy import RoundEnergy, SplitEnergy
from automaton_gui.screens.StageModel import BONUS_CHOOSE, BONUS_HIDDEN, BONUS_OFF, EnergyConfig, StageType

# The stage picker's live preview, without widgets: what an amount, bonus and units per run
# turn into (the energy spent and the runs), and the Optimize pick. Same rules as AHK's
# StageDatabaseCore, which still does the authoritative math after the reply.

NO_BREAK_SPACE = " "


def BonusAmount(energy: EnergyConfig, stageType: StageType, bonusOn: bool) -> int:
    # The bonus only exists while the checkbox does: "claimed" and "none"
    # both mean AHK adds nothing and rounds on its plain branch, so adding
    # one here would inflate the preview.
    if energy.bonus.state != BONUS_CHOOSE or stageType.bonusMode == BONUS_HIDDEN:
        return 0
    if stageType.bonusMode == BONUS_OFF or not bonusOn:
        return energy.bonus.off
    return energy.bonus.on


def SpentAndRuns(
    amount: int, stageType: StageType, energy: EnergyConfig, bonusOn: bool, maxUnits: int
) -> tuple[int, list[int]]:
    bonus = BonusAmount(energy, stageType, bonusOn)
    if bonus:
        spent = RoundEnergy(amount, stageType.step, stageType.maxAmount, bonus, stageType.bonusStep) + bonus
    else:
        spent = RoundEnergy(amount, stageType.step, stageType.maxAmount, roundUp=energy.previewRoundsUp)
    return spent, SplitEnergy(spent, stageType.step, maxUnits, energy.split)


def RunsSummary(runs: list[int]) -> str:
    """The run count, then each stretch of equal runs as "count x energy": 19 (18 x 100, 1 x 60).
    The spaces inside a stretch do not break, so a wrapped line never splits one."""
    if not runs:
        return "0"
    groups: list[list[int]] = []
    for run in runs:
        if groups and (groups[-1][1] == run):
            groups[-1][0] += 1
        else:
            groups.append([1, run])
    stretches = ", ".join(f"{count}{NO_BREAK_SPACE}x{NO_BREAK_SPACE}{energy}" for count, energy in groups)
    return f"{len(runs)} ({stretches})"


def OptimalRuns(amount: int, stageType: StageType, energy: EnergyConfig, fixedUnits: int) -> tuple[bool, int]:
    """The (bonusOn, units per run) needing the fewest runs.

    Same ranking as the manager (games/zzz/battery.py optimize): fewest runs,
    then the evenest split (no menu re-navigation between runs, and no tiny
    stub), then the smaller run since fewer units is easier combat, then the
    most energy. `fixedUnits` is the units per run of a type the user cannot change."""
    fixed = not stageType.unitsAdjustable
    # Area Patrol / Expert Challenge never consume espresso's +1 bonus, so
    # Special is always the better coffee and the palette is not ours to widen.
    bonusChoices = (False,) if fixed else (True, False)
    unitsChoices = (fixedUnits,) if fixed else tuple(range(1, energy.unitsCap + 1))
    best = None
    for bonusOn in bonusChoices:
        for units in unitsChoices:
            spent, runs = SpentAndRuns(amount, stageType, energy, bonusOn, units)
            key = ((1, 0, 0, 0, 0, 0) if not runs else
                   (0, len(runs), max(runs) - min(runs), max(runs), -spent, -units))
            if best is None or key < best[0]:
                best = (key, bonusOn, units)
    _key, bonusOn, units = best
    return bonusOn, units
