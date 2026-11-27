from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from automaton_gui.screens.AccountsFile import ACCOUNT_PREFIX
from automaton_gui.screens.IniFile import IniApply, IniRead

# The stage picker's per-stage team: which teams an account can pick (those with a squad
# preset slot set), the team each stage remembers, and where both live in Accounts.ini.
# AHK sends the teams in the config block (`stageTeams`); a game without teams sends none
# and the picker hides the team block. A stage with no remembered team uses the
# launcher's team.
#
# Stored per account as `<key>=<typeId>-<stageId>:<teamId>,...`; AHK reads the same key
# when it loads the team for a run.


@dataclass(frozen=True)
class TeamOption:
    id: int
    label: str
    images: tuple[str, ...] = ()
    slotKey: str = ""  # the account key holding the team's squad preset slot; 0 = disabled
    enabledKey: str = ""  # the account key of "I have this team"
    mindscapeKey: str = ""  # the account key of the main agent's mindscape; shared by teams with the same agent
    mindscapeLabel: str = ""
    variants: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (label, images) per mindscape level, 0 first

    def AtMindscape(self, mindscape: int) -> tuple[str, tuple[str, ...]]:
        """The label and portraits the team plays with at `mindscape`; the payload's own when it sent no variants."""
        if 0 <= mindscape < len(self.variants):
            return self.variants[mindscape]
        return self.label, self.images


def _Variants(raw: list | None) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        (str(v.get("label", "")), tuple(str(a.get("image", "")) for a in v.get("agents", [])))
        for v in (raw or [])
    )


@dataclass(frozen=True)
class StageTeamsConfig:
    key: str = ""
    defaultTeam: int = 0
    teams: tuple[TeamOption, ...] = ()
    placeholder: str = ""  # art shown where the portraits go until a stage is picked
    defaultKey: str = ""  # the account key of the team the launcher and the macro menu fight with


@dataclass
class TeamChoice:
    """What one picker shows: the account's teams, the fallback and the remembered picks."""
    teams: list[TeamOption]
    defaultTeam: int
    saved: dict[tuple[int, int], int] = field(default_factory=dict)
    onSave: Callable[[int, int, int], None] | None = None
    placeholder: str = ""

    def TeamFor(self, typeID: int, stageID: int) -> int:
        ids = [team.id for team in self.teams]
        saved = self.saved.get((typeID, stageID), 0)
        if saved in ids:
            return saved
        return self.defaultTeam if self.defaultTeam in ids else ids[0]


def ParseStageTeams(raw: dict | None) -> StageTeamsConfig:
    raw = raw or {}
    teams = tuple(
        TeamOption(
            int(t["id"]),
            str(t.get("label", "")),
            tuple(str(a.get("image", "")) for a in t.get("agents", [])),
            str(t.get("slot_key", "")),
            str(t.get("enabled_key", "")),
            str(t.get("mindscape_key", "")),
            str(t.get("mindscape_label", "")),
            _Variants(t.get("by_mindscape")),
        )
        for t in raw.get("teams", [])
    )
    return StageTeamsConfig(
        str(raw.get("key", "")), int(raw.get("default", 0) or 0), teams, str(raw.get("placeholder", "")),
        str(raw.get("default_key", "")))


def DecodeStageTeams(text: str) -> dict[tuple[int, int], int]:
    saved = {}
    for entry in (text or "").split(","):
        stagePart, _sep, teamPart = entry.strip().partition(":")
        typePart, _sep, idPart = stagePart.partition("-")
        if typePart.isdigit() and idPart.isdigit() and teamPart.isdigit():
            saved[(int(typePart), int(idPart))] = int(teamPart)
    return saved


def EncodeStageTeams(saved: dict[tuple[int, int], int]) -> str:
    return ",".join(f"{typeID}-{stageID}:{teamID}" for (typeID, stageID), teamID in sorted(saved.items()))


def ActiveAccountSection(confFile: str | Path) -> str:
    return f"{ACCOUNT_PREFIX}{IniRead(confFile, 'General', 'activeAccount', '0') or '0'}"


def TeamChoiceFor(
    config: StageTeamsConfig, accountsFile: str | Path, section: str, defaultTeam: int | None = None,
) -> TeamChoice | None:
    """The account's picker data, or None when it has no team to pick (the block hides)."""
    if not config.key or not accountsFile:
        return None
    teams = [team for team in config.teams if _Slot(accountsFile, section, team.slotKey) > 0]
    if not teams:
        return None
    saved = DecodeStageTeams(IniRead(accountsFile, section, config.key, ""))

    def OnSave(typeID: int, stageID: int, teamID: int) -> None:
        current = DecodeStageTeams(IniRead(accountsFile, section, config.key, ""))
        current[(typeID, stageID)] = teamID
        IniApply(accountsFile, {(section, config.key): EncodeStageTeams(current)})

    fallback = config.defaultTeam if defaultTeam is None else defaultTeam
    return TeamChoice(teams, fallback, saved, OnSave, config.placeholder)


def _Slot(accountsFile: str | Path, section: str, key: str) -> int:
    value = IniRead(accountsFile, section, key, "0").strip() if key else "0"
    return int(value) if value.isdigit() else 0
