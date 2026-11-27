from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

STAMP_FORMAT = "%Y%m%d%H%M%S"


@dataclass
class LockDef:
    id: str
    reset: str = "daily"
    cooldownHours: int = 0
    quotaMax: int = 0
    quotaPeriod: str = "weekly"
    internal: bool = False
    group: str = ""
    parent: str = ""

    @property
    def hasQuota(self) -> bool:
        return self.quotaMax > 0


@dataclass
class HistoryEntry:
    at: datetime | None
    action: str
    by: str
    count: int


@dataclass
class LockState:
    lockedAt: datetime | None = None
    unlocksAt: datetime | None = None
    count: int = 0
    countResetsAt: datetime | None = None
    ignored: bool = False
    definition: LockDef | None = None
    history: list[HistoryEntry] = field(default_factory=list)

    def IsHeld(self, now: datetime) -> bool:
        return self.unlocksAt is not None and self.unlocksAt > now

    def IsBlocking(self, now: datetime) -> bool:
        return self.IsHeld(now) and not self.ignored

    def CurrentCount(self, now: datetime) -> int:
        if self.countResetsAt is None or self.countResetsAt <= now:
            return 0
        return self.count


def ParseStamp(stamp: object) -> datetime | None:
    try:
        return datetime.strptime(str(stamp), STAMP_FORMAT)
    except ValueError:
        return None


def ParseDefinitions(raw: list[dict]) -> list[LockDef]:
    defs = []
    for item in raw:
        quota = item.get("quota") or {}
        defs.append(
            LockDef(
                id=item["id"],
                reset=item.get("reset", "daily"),
                cooldownHours=int(item.get("cooldown_hours", 0)),
                quotaMax=int(quota.get("max", 0)),
                quotaPeriod=quota.get("period", "weekly"),
                internal=bool(item.get("internal", False)),
                group=item.get("group", ""),
                parent=item.get("parent", ""),
            )
        )
    return defs


def _ParseDefinition(lockId: str, raw: dict) -> LockDef | None:
    """The definition a lock carries in Locks.json, None for a node written before it had one."""
    if not raw:
        return None
    return LockDef(
        id=lockId,
        reset=raw.get("reset", "daily"),
        cooldownHours=int(raw.get("cooldown_hours", 0)),
        quotaMax=int(raw.get("count_max", 0)) if raw.get("count_enabled") else 0,
        quotaPeriod=raw.get("count_period") or "weekly",
        internal=bool(raw.get("internal", False)),
        group=raw.get("group", ""),
        parent=raw.get("parent", ""),
    )


def _ParseState(lockId: str, raw: dict) -> LockState:
    return LockState(
        lockedAt=ParseStamp(raw.get("locked_at", "")),
        unlocksAt=ParseStamp(raw.get("unlocks_at", "")),
        count=int(raw.get("count", 0)),
        countResetsAt=ParseStamp(raw.get("count_resets_at", "")),
        ignored=bool(raw.get("ignore_enabled", False)),
        definition=_ParseDefinition(lockId, raw.get("definition", {})),
        history=[
            HistoryEntry(ParseStamp(h.get("at", "")), h.get("action", ""), h.get("by", ""), int(h.get("count", 0)))
            for h in raw.get("history", [])
        ],
    )


def ReadStates(file: str | Path, account: str) -> dict[str, LockState]:
    """The locks of one account from Locks.json, by lock id; {} when the file or the account is absent."""
    if not file or not Path(file).is_file():
        return {}
    with open(file, encoding="utf-8") as handle:
        root = json.load(handle)
    return {lockId: _ParseState(lockId, raw) for lockId, raw in root.get("accounts", {}).get(str(account), {}).items()}
