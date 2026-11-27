"""Checks on an exe path the user picked: that it is an .exe that exists and, for the game, the game's own one."""

from __future__ import annotations

import os

from automaton_gui.I18n import T


def ExeProblem(path: str, strings: dict | None, required: bool, names: tuple[str, ...] = ()) -> str:
    """What is wrong with `path`, "" when nothing. `names`: the file names it may have (any case)."""
    if not path:
        return T(strings, "exe_check.missing", "Pick the .exe file.") if required else ""
    if not path.lower().endswith(".exe"):
        return T(strings, "exe_check.not_exe", "This is not an .exe file.")
    if names and (os.path.basename(path).lower() not in {name.lower() for name in names}):
        return T(strings, "exe_check.wrong_name", "Pick {names}.", names=" or ".join(names))
    if not os.path.isfile(path):
        return T(strings, "exe_check.no_file", "This file does not exist.")
    return ""
