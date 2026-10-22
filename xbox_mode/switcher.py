"""Task switcher state: the open windows, the selected one, and what A and X do to it. No drawing here."""
from typing import Callable, List, Optional, Sequence

from .windows_list import WindowEntry


class TaskSwitcher:
    def __init__(
        self,
        provider: Callable[[], Sequence[WindowEntry]],
        activate: Callable[[int], None],
        close: Callable[[int], None],
    ) -> None:
        self._provider = provider
        self._activate = activate
        self._close = close
        self.open = False
        self._items: List[WindowEntry] = []
        self._index = 0

    @property
    def items(self) -> List[WindowEntry]:
        return list(self._items)

    @property
    def index(self) -> int:
        return self._index

    def toggle(self) -> bool:
        self.open = not self.open
        if self.open:
            self.refresh()
        return self.open

    def refresh(self) -> None:
        self._items = list(self._provider())
        self._index = min(self._index, max(0, len(self._items) - 1))

    def move(self, dx: int) -> None:
        if self._items:
            self._index = min(max(self._index + dx, 0), len(self._items) - 1)

    def selected(self) -> Optional[WindowEntry]:
        return self._items[self._index] if self._items else None

    def activate(self) -> None:
        """A: bring the selected window to the front and leave the switcher."""
        item = self.selected()
        self.open = False
        if item is not None:
            self._activate(item.hwnd)

    def close_selected(self) -> None:
        """X: close the selected window (like Close App in Xbox mode) and keep the switcher open."""
        item = self.selected()
        if item is None:
            return
        self._close(item.hwnd)
        del self._items[self._index]
        self._index = min(self._index, max(0, len(self._items) - 1))

    def close(self) -> None:
        self.open = False
