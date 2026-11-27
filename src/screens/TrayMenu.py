from __future__ import annotations

import itertools

from PySide6.QtGui import QAction

from automaton_gui.framework.Window import GuiApp
from automaton_gui.screens.ConfigMenu import ConfigMenuData, BuildConfigMenus


class TrayMenuHost(GuiApp):
    """A window that is never shown: it only owns the menu bar BuildConfigMenus
    fills, so the tray menu is the very same Configuration / Locks / Theme / Help
    structure the macro and launch windows have."""

    title = "Tray menu"

    def __init__(self, config: ConfigMenuData) -> None:
        self._config = config
        super().__init__(strings=config.strings)

    def Menu(self) -> None:
        BuildConfigMenus(self, self._config)

    def HasOpenEditors(self) -> bool:
        return any(editor.isVisible() for editor in self._configEditors)

    def Serialize(self) -> tuple[list[dict], dict[int, QAction]]:
        """The menu bar as a tree AHK can paint, plus the action behind every
        leaf id so a click coming back can be triggered."""
        actions: dict[int, QAction] = {}
        ids = itertools.count(1)

        def Walk(level: list[QAction]) -> list[dict]:
            nodes = []
            for action in level:
                if action.isSeparator():
                    nodes.append({"sep": 1})
                    continue
                node = {
                    "label": action.text(),
                    "enabled": int(action.isEnabled()),
                    "checked": int(action.isCheckable() and action.isChecked()),
                }
                submenu = action.menu()
                if submenu is not None:
                    node["children"] = Walk(submenu.actions())
                else:
                    node["id"] = next(ids)
                    actions[node["id"]] = action
                nodes.append(node)
            return nodes

        return Walk(self.menuBar().actions()), actions
