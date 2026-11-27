from __future__ import annotations

from dataclasses import dataclass

from automaton_gui.Energy import SPLIT_EVEN

# The stage picker's data: the stage types and stages AHK sends in the show_stage_select
# payload (Python never reads the AHK stage DB), the game's energy rules and the saved pick.

ENERGY = "energy"
COUNT = "count"

BONUS_CHOOSE = "choose"   # the user toggles between the on and off bonus
BONUS_OFF = "off"         # shown, but locked to the off bonus
BONUS_HIDDEN = "hidden"

BONUS_NONE = "none"
BONUS_CLAIMED = "claimed"

FACT_SPENT = "spent"
FACT_UNITS = "units"
FACT_RUNS = "runs"

AMOUNT_RANGE_ENERGY = (0, 9999)


@dataclass(frozen=True)
class StageType:
    id: int
    name: str
    # ENERGY = multi-digit field broken down into runs; COUNT = a plain run count
    # (minAmount..max_amount). Drives the amount label + input limit.
    unit: str = ENERGY
    # Energy per unit (a ZZZ card, an HSR attempt); 0 = nothing to break down.
    step: int = 0
    maxUnits: int = 1
    unitsAdjustable: bool = False
    minAmount: int = 0
    maxAmount: int = AMOUNT_RANGE_ENERGY[1]
    defaultAmount: int = 0
    bonusMode: str = BONUS_HIDDEN
    bonusStep: int = 0
    # Why the type cannot run right now; greys the amount and Start.
    unavailable: str = ""
    badge: str = ""  # drop-bonus pill ("x2"/"x3"), empty for none


@dataclass(frozen=True)
class BonusConfig:
    # state: BONUS_NONE, BONUS_CHOOSE (a toggle between the on and off bonus), or
    # BONUS_CLAIMED. checked is the toggle's initial state.
    state: str = BONUS_NONE
    on: int = 0
    off: int = 0
    checked: bool = False


@dataclass(frozen=True)
class EnergyConfig:
    split: str = SPLIT_EVEN
    previewRoundsUp: bool = False
    facts: tuple = (FACT_SPENT, FACT_RUNS)
    stepper: bool = False
    # the current cap for types whose units per run the user (or Optimize) can change
    maxUnits: int = 1
    unitsCap: int = 1
    bonus: BonusConfig = BonusConfig()


@dataclass(frozen=True)
class Stage:
    id: int
    name: str
    # Optional image path AHK resolves from its DB and puts in the payload; Python
    # only loads it as a pixmap, never derives it.
    icon: str = ""
    # Overrides the type's units per run for this stage alone; 0 = the type's.
    maxUnits: int = 0
    badge: str = ""
    # group: a non-selectable heading the list shows above its stages. label: what
    # the list shows for the stage under it, when the full name would repeat the group.
    group: str = ""
    label: str = ""


@dataclass(frozen=True)
class StageDefaults:
    typeID: int = 0
    stageID: int = 0
    amount: int = 0
