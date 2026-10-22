"""Controller state shared by the real input source and by tests."""
from dataclasses import dataclass
from typing import FrozenSet, Optional, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class ControllerState:
    # Sticks and D-pad use screen coordinates: x grows to the right, y grows downward.
    left: Tuple[float, float] = (0.0, 0.0)
    right: Tuple[float, float] = (0.0, 0.0)
    lt: float = 0.0
    rt: float = 0.0
    buttons: FrozenSet[str] = frozenset()
    dpad: Tuple[int, int] = (0, 0)


class ControllerSource(Protocol):
    def read(self) -> Optional[ControllerState]:
        """Return the current state, or None when no controller is connected."""


class ReplaySource:
    """Replays a fixed sequence of states, then reports no controller."""

    def __init__(self, states: Sequence[ControllerState]) -> None:
        self._states = list(states)
        self._index = 0

    def read(self) -> Optional[ControllerState]:
        if self._index >= len(self._states):
            return None
        state = self._states[self._index]
        self._index += 1
        return state
