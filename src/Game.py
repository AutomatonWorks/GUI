"""The game this GUI belongs to. The game package registers its conf module on
import, before any screen is imported; screens read it as `GameConf.APP_NAME`
or `from automaton_gui.game import PRESET_SKIP_KEY`."""

from __future__ import annotations

from types import ModuleType

_conf: ModuleType | None = None


def Register(conf: ModuleType) -> None:
    global _conf
    _conf = conf


def Module() -> ModuleType:
    if _conf is None:
        raise RuntimeError("no game registered: import the game package before the GUI screens")
    return _conf


def __getattr__(name: str):
    return getattr(Module(), name)
