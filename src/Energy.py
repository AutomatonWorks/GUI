from __future__ import annotations

# Energy -> runs math every game's stage picker shares. A game only sends the
# numbers (StageDatabaseCore's energy hooks on the AHK side); StageDatabaseCore
# RoundEnergy / SplitEnergy run the same rules for the authoritative pass.

SPLIT_EVEN = "even"
SPLIT_FILL = "fill"


def RoundEnergy(amount: int, step: int, maxAmount: int, bonus: int = 0, bonusStep: int = 0,
                 roundUp: bool = True) -> int:
    if bonus:
        if amount == 0:
            return 0
        return max(0, amount - (amount + bonus) % bonusStep)
    if amount < step:
        return step if roundUp else 0
    return min(maxAmount, amount - amount % step)


def SplitEnergy(total: int, step: int, maxUnits: int, mode: str) -> list[int]:
    if total <= 0 or step <= 0:
        return []
    if mode == SPLIT_FILL:
        units = total // step
        runs = [maxUnits * step] * (units // maxUnits)
        if units % maxUnits:
            runs.append(units % maxUnits * step)
        return runs
    return _EvenSplit(total, [units * step for units in range(maxUnits, 0, -1)])


def _EvenSplit(value: int, denominations: list[int]) -> list[int]:
    combo: dict[int, int] = {}
    remaining = value
    turns = 0
    for denom in denominations:
        count = remaining // denom
        if count > 0:
            combo[denom] = count
            remaining -= count * denom
            turns += count
    # one size for every run when that costs no extra run: 160 is 80,80, not 100,60
    for denom in denominations:
        if value % denom == 0:
            count = value // denom
            if count <= turns:
                combo = {denom: count}
                turns = count
    runs: list[int] = []
    for denom, count in combo.items():
        runs.extend([denom] * count)
    runs.sort(reverse=True)
    return runs
