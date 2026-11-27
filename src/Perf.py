from __future__ import annotations

import time


def MetricsEnabled(confFile: str) -> bool:
    """[Dev] Dev and PerfMetrics are both 1 in the conf."""
    from automaton_gui.screens.IniFile import IniRead

    if not confFile:
        return False
    return IniRead(confFile, "Dev", "Dev", "0").strip() == "1" and IniRead(confFile, "Dev", "perf_metrics", "0").strip() == "1"


class PerfTimer:
    """Wall-clock laps for one GUI-host operation, reported to AHK as a `perf` notification
    so they land in the same log as the AHK-side [PERF] lines."""

    def __init__(self, label: str, enabled: bool) -> None:
        self.enabled = enabled
        self.label = label
        self._laps: list[str] = []
        self._startedAt = time.perf_counter()
        self._lastLapAt = self._startedAt

    def Lap(self, name: str) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        self._laps.append(f"{name} {(now - self._lastLapAt) * 1000:.1f} ms")
        self._lastLapAt = now

    def data(self) -> dict:
        total = (time.perf_counter() - self._startedAt) * 1000
        return {"label": self.label, "total": f"{total:.1f}", "laps": ", ".join(self._laps)}
