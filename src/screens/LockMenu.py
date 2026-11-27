from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from PySide6.QtWidgets import QApplication, QInputDialog, QMenu

from automaton_gui.I18n import T
from automaton_gui.Locks import LockDef, LockState, ParseDefinitions, ReadStates
from automaton_gui.screens.AccountsFile import ACCOUNT_PREFIX, DisplayAccountName
from automaton_gui.screens.IniFile import IniRead
from automaton_gui.Version import VersionedTitle

DISPLAY_FORMAT = "%Y-%m-%d %H:%M"
HISTORY_FORMAT = "%m-%d %H:%M"

# send(action, which, value): action is lock / release / release_all / ignore / unignore / set_count,
# which is the lock id ("" for release_all), value the new counter for set_count
LockSender = Callable[..., None]


def ActiveAccount(confFile: str) -> str:
    return IniRead(confFile, "General", "activeAccount", "0").strip() or "0"


def AskCount(strings: dict, name: str, current: int, maximum: int) -> int | None:
    """The counter the user types in, None when they cancel."""
    value, accepted = QInputDialog.getInt(
        QApplication.activeWindow(),
        VersionedTitle(T(strings, "config_menu.lock_set_count_title", "Set counter")),
        T(strings, "config_menu.lock_set_count_label", "Counter for {lock} (0 to {max}):", lock=name, max=maximum),
        current, 0, maximum,
    )
    return value if accepted else None


def _Remaining(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 1)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _LockName(strings: dict, lockId: str) -> str:
    return T(strings, f"config_menu.lock_name.{lockId}", lockId)


def _Why(strings: dict, defn: LockDef, state: LockState, now: datetime) -> str:
    if state.ignored:
        return T(strings, "config_menu.lock_why_ignored", "Why: ignored, it never blocks")
    if not state.IsHeld(now):
        return ""
    if defn.hasQuota and state.CurrentCount(now) >= defn.quotaMax:
        return T(
            strings, "config_menu.lock_why_quota", "Why: quota reached ({count}/{max})",
            count=state.CurrentCount(now), max=defn.quotaMax,
        )
    locks = [entry for entry in state.history if entry.action == "lock"]
    by = locks[-1].by if locks else "?"
    return T(strings, "config_menu.lock_why_by", "Why: locked by {by}", by=by)


def _Label(strings: dict, defn: LockDef, state: LockState, now: datetime) -> str:
    name = _LockName(strings, defn.id)
    if state.ignored:
        label = T(strings, "config_menu.lock_ignored", "{lock} [Ignored]", lock=name)
    elif state.IsHeld(now):
        label = T(strings, "config_menu.lock_locked", "{lock} [Locked]", lock=name)
    else:
        label = T(strings, "config_menu.lock_unlocked", "{lock} [Unlocked]", lock=name)
    if defn.hasQuota:
        label += " " + T(
            strings, "config_menu.lock_count_suffix", "({count}/{max})",
            count=state.CurrentCount(now), max=defn.quotaMax,
        )
    return label


def _HistoryRow(defn: LockDef, entry) -> str:
    when = entry.at.strftime(HISTORY_FORMAT) if entry.at is not None else "?"
    row = f"{when}  {entry.action}  {entry.by}"
    if defn.hasQuota:
        row += f"  {entry.count}/{defn.quotaMax}"
    return row


def _SetCount(strings: dict, defn: LockDef, state: LockState, now: datetime, send: LockSender) -> None:
    value = AskCount(strings, _LockName(strings, defn.id), state.CurrentCount(now), defn.quotaMax)
    if value is not None:
        send("set_count", defn.id, str(value))


def _AddLockSubmenu(
    parent: QMenu, strings: dict, defn: LockDef, state: LockState, now: datetime, send: LockSender, byParent: dict
) -> None:
    submenu = parent.addMenu(_Label(strings, defn, state, now))
    submenu.setToolTipsVisible(True)
    why = _Why(strings, defn, state, now)
    if why:
        submenu.menuAction().setToolTip(why)

    held = state.IsHeld(now)
    if held:
        action = submenu.addAction(T(strings, "config_menu.release_lock", "Release"))
        action.triggered.connect(lambda checked=False: send("release", defn.id))
    else:
        key = "config_menu.lock_lock_count" if defn.hasQuota else "config_menu.lock_lock"
        default = "Lock (+1)" if defn.hasQuota else "Lock"
        action = submenu.addAction(T(strings, key, default))
        action.triggered.connect(lambda checked=False: send("lock", defn.id))

    ignore = submenu.addAction(T(strings, "config_menu.lock_ignore", "Ignore"))
    ignore.setCheckable(True)
    ignore.setChecked(state.ignored)
    ignore.triggered.connect(lambda checked=False: send("unignore" if state.ignored else "ignore", defn.id))

    if defn.hasQuota:
        setCount = submenu.addAction(T(strings, "config_menu.lock_set_count", "Set counter..."))
        setCount.triggered.connect(lambda checked=False: _SetCount(strings, defn, state, now, send))

    submenu.addSeparator()
    history = submenu.addMenu(T(strings, "config_menu.lock_history", "History"))
    if state.history:
        for entry in reversed(state.history):
            history.addAction(_HistoryRow(defn, entry)).setEnabled(False)
    else:
        history.addAction(T(strings, "config_menu.lock_history_empty", "No history")).setEnabled(False)

    for childDefn, childState in byParent.get(defn.id, []):
        _AddLockSubmenu(submenu, strings, childDefn, childState, now, send, byParent)

    info = []
    if state.lockedAt is not None and held:
        when = state.lockedAt.strftime(DISPLAY_FORMAT)
        info.append(T(strings, "config_menu.lock_locked_at", "Locked: {when}", when=when))
    if held:
        info.append(T(
            strings, "config_menu.lock_releases_at", "Releases: {when} (in {remaining})",
            when=state.unlocksAt.strftime(DISPLAY_FORMAT), remaining=_Remaining(state.unlocksAt - now),
        ))
    if why:
        info.append(why)
    if info:
        submenu.addSeparator()
        for text in info:
            submenu.addAction(text).setEnabled(False)


def _Fill(menu: QMenu, strings: dict, entries: list, now: datetime, send: LockSender) -> None:
    """A lock submenu per public lock in declaration order, a lock with a parent inside its parent's submenu,
    then the internal ones under their own submenu."""
    menu.setToolTipsVisible(True)
    ids = {defn.id for defn, _state in entries}
    byParent: dict[str, list] = {}
    roots = []
    for entry in entries:
        if entry[0].parent in ids and entry[0].parent != entry[0].id:
            byParent.setdefault(entry[0].parent, []).append(entry)
        else:
            roots.append(entry)

    for defn, state in roots:
        if not defn.internal:
            _AddLockSubmenu(menu, strings, defn, state, now, send, byParent)

    internal = [entry for entry in roots if entry[0].internal]
    if internal:
        internalMenu = menu.addMenu(T(strings, "config_menu.lock_internal", "Internal locks"))
        internalMenu.setToolTipsVisible(True)
        for defn, state in internal:
            _AddLockSubmenu(internalMenu, strings, defn, state, now, send, byParent)


def PopulateLocksMenu(menu: QMenu, data, strings: dict, send: LockSender) -> None:
    now = datetime.now()
    account = ActiveAccount(data.confFile)
    states = ReadStates(data.locksFile, account)

    entries = []
    for catalogDefn in ParseDefinitions(data.locks):
        state = states.get(catalogDefn.id, LockState())
        entries.append((state.definition or catalogDefn, state))

    _Fill(menu, strings, [entry for entry in entries if not entry[0].group], now, send)
    for group in dict.fromkeys(defn.group for defn, _state in entries if defn.group):
        groupMenu = menu.addMenu(T(strings, f"config_menu.lock_group.{group}", group))
        _Fill(groupMenu, strings, [entry for entry in entries if entry[0].group == group], now, send)

    menu.addSeparator()
    accountName = DisplayAccountName(data.accountsFile, f"{ACCOUNT_PREFIX}{account}")
    releaseAll = menu.addAction(
        T(strings, "config_menu.release_all_account", "Release all {account} locks", account=accountName)
    )
    releaseAll.setEnabled(any(state.IsHeld(now) for _defn, state in entries))
    releaseAll.triggered.connect(lambda checked=False: send("release_all", ""))
