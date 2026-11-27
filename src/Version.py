from __future__ import annotations

from pathlib import Path

from automaton_gui import Game


def _FindVersionFile() -> Path:
    """VERSION beside the game's registered conf module, or at the game package root
    (the conf module being <package>/gui/game_conf.py)."""
    near = Path(Game.Module().__file__).resolve()
    for candidate in (near.parent / "VERSION", near.parent.parent / "VERSION"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"VERSION not found near {near}")


APP_VERSION = _FindVersionFile().read_text(encoding="ascii").strip()


def VersionedTitle(title: str) -> str:
    """"ZZZ Automaton | Launch Options" -> "ZZZ Automaton v3.2.64 | Launch Options"."""
    name, separator, rest = title.partition(" | ")
    return f"{name} v{APP_VERSION}{separator}{rest}"
