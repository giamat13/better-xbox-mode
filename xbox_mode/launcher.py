"""Grid launcher state: pure logic, no drawing and no input devices."""
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .launcher_apps import App


@dataclass(frozen=True)
class Tile:
    name: str
    selected: bool


class Launcher:
    def __init__(self, apps: Sequence[App], columns: int = 4) -> None:
        self._apps: List[App] = list(apps)
        self._columns = max(1, columns)
        self._index = 0
        self.open = False

    def toggle(self) -> bool:
        self.open = not self.open
        return self.open

    def close(self) -> None:
        self.open = False

    def move(self, dx: int, dy: int) -> None:
        if not self._apps:
            return
        row, column = divmod(self._index, self._columns)
        rows = (len(self._apps) - 1) // self._columns + 1
        column = min(max(column + dx, 0), self._columns - 1)
        row = min(max(row + dy, 0), rows - 1)
        self._index = min(row * self._columns + column, len(self._apps) - 1)

    def select(self) -> Optional[App]:
        if not self._apps:
            return None
        self.open = False
        return self._apps[self._index]

    def tiles(self) -> Tuple[Tile, ...]:
        return tuple(Tile(app.name, index == self._index) for index, app in enumerate(self._apps))
