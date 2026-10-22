"""Pure input shaping: stick response, button edges and the toggle chord."""
import math
from typing import FrozenSet, Iterable, Optional, Tuple


def shape_stick(x: float, y: float, deadzone: float, exponent: float) -> Tuple[float, float]:
    magnitude = math.hypot(x, y)
    if magnitude <= deadzone:
        return 0.0, 0.0
    scaled = min((magnitude - deadzone) / (1.0 - deadzone), 1.0)
    factor = (scaled ** exponent) / magnitude
    return x * factor, y * factor


class ButtonEdges:
    def __init__(self) -> None:
        self._previous: FrozenSet[str] = frozenset()

    def update(self, buttons: FrozenSet[str]) -> Tuple[FrozenSet[str], FrozenSet[str]]:
        pressed = buttons - self._previous
        released = self._previous - buttons
        self._previous = buttons
        return pressed, released


class ChordTimer:
    """Reports True once when every named button has been held for hold_seconds."""

    def __init__(self, names: Iterable[str], hold_seconds: float) -> None:
        self._names = frozenset(names)
        self._hold = hold_seconds
        self._since: Optional[float] = None
        self._fired = False

    def update(self, buttons: FrozenSet[str], now: float) -> bool:
        if not self._names <= buttons:
            self._since = None
            self._fired = False
            return False
        if self._since is None:
            self._since = now
        if not self._fired and now - self._since >= self._hold:
            self._fired = True
            return True
        return False
