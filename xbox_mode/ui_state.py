"""Turns the launcher, keyboard and switcher models into one JSON-friendly snapshot for the HTML UI."""
import datetime
from typing import Any, Dict

from .keyboard_model import OnScreenKeyboard
from .launcher import Launcher
from .switcher import TaskSwitcher


def build_state(launcher: Launcher, on_screen: OnScreenKeyboard, switcher: TaskSwitcher) -> Dict[str, Any]:
    clock = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
    if switcher.open:
        return {
            "mode": "switcher",
            "clock": clock,
            "windows": [{"title": item.title} for item in switcher.items],
            "selected": switcher.index,
        }
    if on_screen.open:
        row, column = on_screen.selection()
        return {
            "mode": "keyboard",
            "language": on_screen.language,
            "rows": [[{"label": key.label, "action": key.action} for key in line] for line in on_screen.rows()],
            "row": row,
            "column": column,
        }
    if launcher.open:
        tiles = launcher.tiles()
        return {
            "mode": "home",
            "clock": clock,
            "apps": [tile.name for tile in tiles],
            "selected": next((index for index, tile in enumerate(tiles) if tile.selected), 0),
        }
    return {"mode": "none"}
