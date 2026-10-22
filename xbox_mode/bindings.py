"""Default button bindings. Action values: mouse:<button>, key:<name>, osk, launcher."""
from typing import Dict, Tuple

DEFAULT_BINDINGS: Dict[str, str] = {
    "A": "mouse:left",
    "B": "mouse:right",
    "LS": "mouse:middle",
    "X": "key:backspace",
    "Y": "osk",
    "START": "key:enter",
    "BACK": "key:escape",
    "GUIDE": "launcher",
}

DPAD_KEYS: Dict[Tuple[int, int], str] = {
    (0, -1): "up",
    (0, 1): "down",
    (-1, 0): "left",
    (1, 0): "right",
}

TOGGLE_CHORD = ("LB", "RB")
