"""Mouse and keyboard output: sub-pixel accumulation, held-state tracking, D-pad repeat."""
from typing import List, Protocol, Set, Tuple

KEY_NAMES = frozenset(
    {"enter", "escape", "backspace", "tab", "space", "up", "down", "left", "right", "pageup", "pagedown"}
)
MOUSE_BUTTONS = frozenset({"left", "right", "middle"})
DIRECTIONS = frozenset({(0, -1), (0, 1), (-1, 0), (1, 0)})


class InputBackend(Protocol):
    def move_relative(self, dx: int, dy: int) -> None: ...
    def button(self, name: str, down: bool) -> None: ...
    def wheel(self, ticks: int) -> None: ...
    def key(self, name: str, down: bool) -> None: ...


class MouseOutput:
    def __init__(self, backend: InputBackend) -> None:
        self._backend = backend
        self._pending_x = 0.0
        self._pending_y = 0.0
        self._pending_wheel = 0.0
        self._held: Set[str] = set()

    def move(self, dx: float, dy: float) -> None:
        self._pending_x += dx
        self._pending_y += dy
        whole_x, whole_y = round(self._pending_x), round(self._pending_y)
        if whole_x or whole_y:
            self._backend.move_relative(whole_x, whole_y)
            self._pending_x -= whole_x
            self._pending_y -= whole_y

    def scroll(self, ticks: float) -> None:
        self._pending_wheel += ticks
        whole = round(self._pending_wheel)
        if whole:
            self._backend.wheel(whole)
            self._pending_wheel -= whole

    def press(self, button: str) -> None:
        if button not in MOUSE_BUTTONS:
            raise ValueError(f"unknown mouse button {button!r}")
        if button not in self._held:
            self._held.add(button)
            self._backend.button(button, True)

    def release(self, button: str) -> None:
        if button in self._held:
            self._held.discard(button)
            self._backend.button(button, False)

    def release_all(self) -> None:
        for button in sorted(self._held):
            self.release(button)
        self._pending_x = 0.0
        self._pending_y = 0.0
        self._pending_wheel = 0.0


class KeyboardOutput:
    def __init__(self, backend: InputBackend) -> None:
        self._backend = backend
        self._held: Set[str] = set()

    def tap(self, name: str) -> None:
        self._check(name)
        self._backend.key(name, True)
        self._backend.key(name, False)

    def press(self, name: str) -> None:
        self._check(name)
        if name not in self._held:
            self._held.add(name)
            self._backend.key(name, True)

    def release(self, name: str) -> None:
        if name in self._held:
            self._held.discard(name)
            self._backend.key(name, False)

    def release_all(self) -> None:
        for name in sorted(self._held):
            self.release(name)

    @staticmethod
    def _check(name: str) -> None:
        if name not in KEY_NAMES:
            raise ValueError(f"unknown key {name!r}")


class DpadRepeater:
    """Emits a D-pad direction once when it is pressed, then repeats it while held."""

    def __init__(self, delay: float, interval: float) -> None:
        self._delay = delay
        self._interval = interval
        self._direction: Tuple[int, int] = (0, 0)
        self._next = 0.0

    def update(self, dpad: Tuple[int, int], now: float) -> List[Tuple[int, int]]:
        direction = dpad if dpad in DIRECTIONS else (0, 0)
        if direction != self._direction:
            self._direction = direction
            self._next = now + self._delay
            return [direction] if direction != (0, 0) else []
        if direction != (0, 0) and now >= self._next:
            self._next = now + self._interval
            return [direction]
        return []
