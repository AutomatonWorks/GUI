from __future__ import annotations

from typing import Callable

from automaton_gui.ipc import Message

# Parsers for the show_* payloads AHK sends the host: plain JSON in, the screens'
# dataclasses out. Screen modules are imported lazily, as the host only loads
# the ones a request needs.


def ParseStageTables(rawTypes: list, rawStages: dict, rawBadges: dict):
    """StageType/Stage dataclasses from the stage-DB JSON nested in `config`: the
    stage picker, the account editor's two dropdowns and the launch window's
    "Change..." picker all read them from there."""
    from automaton_gui.screens.StageModel import (
        AMOUNT_RANGE_ENERGY,
        BONUS_HIDDEN,
        ENERGY,
        Stage,
        StageType,
    )

    typeBadges = rawBadges.get("types", {})
    stageBadges = rawBadges.get("stages", {})
    types = [
        StageType(
            t["id"],
            t["name"],
            unit=t.get("unit", ENERGY),
            step=t.get("step", 0),
            maxUnits=t.get("maxUnits", 1),
            unitsAdjustable=bool(t.get("unitsAdjustable", 0)),
            minAmount=t.get("minAmount", 0),
            maxAmount=t.get("maxAmount", AMOUNT_RANGE_ENERGY[1]),
            defaultAmount=t.get("defaultAmount", 0),
            bonusMode=t.get("bonusMode", BONUS_HIDDEN),
            bonusStep=t.get("bonusStep", 0),
            unavailable=t.get("unavailable", ""),
            badge=typeBadges.get(str(t["id"]), ""),
        )
        for t in rawTypes
    ]
    stages = {
        int(k): [Stage(s["id"], s["name"], s.get("icon", ""), s.get("maxUnits", 0),
                       stageBadges.get(f"{k}:{s['id']}", ""), s.get("group", ""), s.get("label", ""))
                  for s in v]
        for k, v in rawStages.items()
    }
    return types, stages


def ParseEnergy(raw: dict):
    """EnergyConfig from the payload's `energy` block (StageDatabaseCore.EnergyPayloadJson)."""
    from automaton_gui.Energy import SPLIT_EVEN
    from automaton_gui.screens.StageModel import BONUS_NONE, BonusConfig, EnergyConfig, FACT_RUNS, FACT_SPENT

    rawBonus = raw.get("bonus", {})
    return EnergyConfig(
        split=raw.get("split", SPLIT_EVEN),
        previewRoundsUp=bool(raw.get("previewRoundsUp", 0)),
        facts=tuple(raw.get("facts", (FACT_SPENT, FACT_RUNS))),
        stepper=bool(raw.get("stepper", 0)),
        maxUnits=raw.get("maxUnits", 1),
        unitsCap=raw.get("unitsCap", 1),
        bonus=BonusConfig(
            state=rawBonus.get("state", BONUS_NONE),
            on=rawBonus.get("on", 0),
            off=rawBonus.get("off", 0),
            checked=bool(rawBonus.get("checked", 0)),
        ),
    )


def ParseStageDefaults(raw: dict | None):
    from automaton_gui.screens.StageModel import StageDefaults

    if not raw:
        return StageDefaults(typeID=0, stageID=0, amount=0)
    return StageDefaults(raw["type_id"], raw["stage_id"], raw["amount"])


def ParseLaunchOptions(data: dict) -> tuple[list, list]:
    """The launch modes and team presets of a show_launch payload."""
    from automaton_gui.screens.Launch import LaunchItem, TeamItem

    options = [
        LaunchItem(o["id"], o["label"], o.get("tip", ""), bool(o.get("preset", 0)), o.get("badge", ""))
        for o in data.get("options", [])
    ]
    teams = [TeamItem(t["id"], t["label"]) for t in data.get("teams", [])]
    return options, teams


def ParseMacroSections(data: dict) -> list:
    from automaton_gui.screens.Macro import MacroItem, MacroSection

    return [
        MacroSection(
            s["title"],
            s.get("columns", 1),
            [MacroItem(it["id"], it["label"]) for it in s.get("items", [])],
            s.get("rows", []),
        )
        for s in data.get("sections", [])
    ]


def ConfigFromPayload(data: dict, notifyAhk: Callable[[Message], None]):
    """The `config` block as ConfigMenuData, or None when the payload has none.

    The config menu bar (Configuration/Locks/Theme/Help) on the launch + macro
    windows opens the Python editors in-process. AHK supplies their dropdown
    data + file paths in `config` (Python stays dumb). The settings-saved and lock
    actions are app-side effects, so they go back out through `notifyAhk` as
    fire-and-forget notifications the GuiBridge handles (settings_saved -> AppBootstrap.apply_settings;
    lock_action {action, which, account, value} -> Lock.Handle;
    data_action {action, path, backup_first} -> DataActions.Handle)."""
    cfg = data.get("config")
    if not cfg:
        return None
    from automaton_gui.screens.ConfigMenu import ConfigMenuData
    from automaton_gui.screens.StageTeam import ParseStageTeams

    stageTypes, stageStages = ParseStageTables(
        cfg.get("types", []), cfg.get("stages", {}), cfg.get("badges", {}))

    def OnSettingsSaved() -> None:
        notifyAhk(Message(type="settings_saved", data={}))

    def OnLockAction(action: str, which: str, account: str, value: str = "") -> None:
        notifyAhk(Message(
            type="lock_action", data={"action": action, "which": which, "account": account, "value": value}))

    def OnDataAction(action: str, path: str = "", backupFirst: bool = False) -> None:
        notifyAhk(Message(
            type="data_action", data={"action": action, "path": path, "backup_first": "1" if backupFirst else "0"}))

    return ConfigMenuData(
        confFile=cfg.get("conf_file", ""),
        savFile=cfg.get("sav_file", ""),
        accountsFile=cfg.get("accounts_file", ""),
        logFile=cfg.get("log_file", ""),
        repoUrl=cfg.get("repo_url", ""),
        languages=cfg.get("languages", []),
        languageDefault=cfg.get("language_default", ""),
        launchModes=cfg.get("launch_modes", []),
        dailiesAreas=cfg.get("dailies_areas", []),
        dailiesDefault=cfg.get("dailies_default", 0),
        stageTypes=stageTypes,
        stageStages=stageStages,
        placeholder=cfg.get("placeholder", ""),
        stageTeams=ParseStageTeams(cfg["stage_teams"]) if cfg.get("stage_teams") else None,
        locks=cfg.get("locks", []),
        locksFile=cfg.get("locks_file", ""),
        backupsDir=cfg.get("backups_dir", ""),
        strings=cfg.get("strings", {}),
        onSettingsSaved=OnSettingsSaved,
        onLockAction=OnLockAction,
        onDataAction=OnDataAction,
    )
