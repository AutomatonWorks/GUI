from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class Message:
    """One request or notification between the macro side and the GUI, in-process."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)


# A window's answer to the request that opened it: reply(type, data).
Reply = Callable[[str, dict[str, Any]], None]

# A message the GUI sends on its own (settings_saved, lock_action, macro_refresh).
Notify = Callable[[Message], None]
