"""Fullscreen app grid. Runs on the controller loop's thread: the loop calls sync() every tick."""
from typing import List, Optional

from .launcher import Launcher

BACKGROUND = "#101010"
TILE = "#262626"
TILE_SELECTED = "#107c10"
TEXT = "#ffffff"


class LauncherWindow:
    def __init__(self) -> None:
        self._root = None
        self._tiles: List = []
        self._visible = False

    def sync(self, launcher: Launcher) -> None:
        if launcher.open and not self._visible:
            self._show()
        elif not launcher.open and self._visible:
            self._hide()
        if self._visible:
            self._render(launcher)
        if self._root is not None:
            self._root.update()

    def close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None
            self._tiles = []
            self._visible = False

    def _show(self) -> None:
        if self._root is None:
            import tkinter as tk

            self._root = tk.Tk()
            self._root.title("Xbox mode")
            self._root.configure(bg=BACKGROUND)
            self._grid = tk.Frame(self._root, bg=BACKGROUND)
            self._grid.pack(expand=True)
            self._status = tk.Label(self._root, bg=BACKGROUND, fg=TEXT, font=("Segoe UI", 16))
            self._status.pack(side="bottom", pady=20)
        self._root.attributes("-fullscreen", True)
        self._root.deiconify()
        self._visible = True

    def _hide(self) -> None:
        if self._root is not None:
            self._root.withdraw()
        self._visible = False

    def _render(self, launcher: Launcher) -> None:
        tiles = launcher.tiles()
        if len(tiles) != len(self._tiles):
            import tkinter as tk

            for widget in self._tiles:
                widget.destroy()
            self._tiles = []
            columns = 4
            for index in range(len(tiles)):
                label = tk.Label(
                    self._grid, width=22, height=4, wraplength=300, font=("Segoe UI", 18), fg=TEXT, bg=TILE
                )
                label.grid(row=index // columns, column=index % columns, padx=12, pady=12)
                self._tiles.append(label)
        for label, tile in zip(self._tiles, tiles):
            label.configure(text=tile.name, bg=TILE_SELECTED if tile.selected else TILE)
        self._status.configure(text="A: open   B: close   Guide: toggle")
