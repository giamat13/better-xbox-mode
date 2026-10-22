"""One hidden Tk root that owns the launcher, the on-screen keyboard and the task switcher.
The controller loop calls sync() every tick."""
from typing import Optional

from .keyboard_model import OnScreenKeyboard
from .launcher import Launcher
from .switcher import TaskSwitcher


class Overlay:
    def __init__(self) -> None:
        self._root = None
        self._launcher_view = None
        self._keyboard_view = None
        self._switcher_view = None

    def sync(
        self,
        launcher: Launcher,
        on_screen: OnScreenKeyboard,
        switcher: Optional[TaskSwitcher] = None,
    ) -> None:
        wants_ui = launcher.open or on_screen.open or (switcher is not None and switcher.open)
        if self._root is None and wants_ui:
            self._create()
        if self._root is None:
            return
        self._launcher_view.sync(launcher)
        self._keyboard_view.sync(on_screen)
        if switcher is not None:
            self._switcher_view.sync(switcher)
        self._root.update()

    def close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None
            self._launcher_view = None
            self._keyboard_view = None
            self._switcher_view = None

    def _create(self) -> None:
        import tkinter as tk

        from .keyboard_ui import KeyboardView
        from .launcher_ui import LauncherView
        from .switcher_ui import SwitcherView

        self._root = tk.Tk()
        self._root.withdraw()
        self._launcher_view = LauncherView(self._root)
        self._keyboard_view = KeyboardView(self._root)
        self._switcher_view = SwitcherView(self._root)
