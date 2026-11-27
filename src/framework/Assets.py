from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

# Locate bundled assets without hard-coding the layout, which differs between the
# dev tree (<game package>/.img/game.ico) and the compiled build (next to the exe in
# images/game.ico). Walk up from the registered game's conf module looking for either folder.
_ICON_DIRS = (".img", "images")


def _FindAsset(name: str) -> Path | None:
    from automaton_gui import Game

    for base in Path(Game.Module().__file__).absolute().parents:
        for folder in _ICON_DIRS:
            candidate = base / folder / name
            if candidate.is_file():
                return candidate
    return None


def AppIcon() -> QIcon:
    """The game window icon (game.ico), or an empty QIcon if it can't be found."""
    path = _FindAsset("game.ico")
    return QIcon(str(path)) if path is not None else QIcon()


def SetTaskbarIdentity(appId: str) -> None:
    """Give the process its own Windows AppUserModelID. Without this, a GUI launched
    through python/pythonw is grouped under the interpreter's identity, so the taskbar
    shows the generic Python icon instead of our window icon (setWindowIcon alone does
    not fix the taskbar). No-op off Windows or if the shell call is unavailable."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appId)
    except (AttributeError, OSError):
        pass
