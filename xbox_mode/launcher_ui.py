"""Fullscreen app launcher drawn on a canvas. Its window belongs to the shared Overlay root."""
import datetime
from typing import Optional, Tuple

from .launcher import Launcher
from .ui_common import BACKGROUND, FONT, MUTED, TEXT, draw_status, rounded

LOGO_GREEN = "#107c10"
TILE = "#1a2129"
TILE_FOCUSED = "#26313c"
FOCUS_RING = "#4fc3f7"
AVATARS = ("#107c10", "#0078d4", "#8764b8", "#ca5010", "#038387", "#c239b3")

# Must match the column count the Launcher uses for D-pad movement.
COLUMNS = 4
TILE_WIDTH = 300
TILE_HEIGHT = 170
GAP = 28
TOP = 150
FOOTER = 90


class LauncherView:
    def __init__(self, root) -> None:
        import tkinter as tk

        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.title("Xbox mode")
        self._window.configure(bg=BACKGROUND)
        self._canvas = tk.Canvas(self._window, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._visible = False
        self._key: Optional[Tuple] = None

    def sync(self, launcher: Launcher) -> None:
        if launcher.open and not self._visible:
            self._show()
        elif not launcher.open and self._visible:
            self._window.withdraw()
            self._visible = False
        if self._visible:
            self._render(launcher)

    def _show(self) -> None:
        self._window.deiconify()
        self._window.attributes("-fullscreen", True)
        self._window.focus_force()
        self._key = None
        self._visible = True

    def _render(self, launcher: Launcher) -> None:
        tiles = launcher.tiles()
        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()
        now = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        selected = next((index for index, tile in enumerate(tiles) if tile.selected), 0)
        key = (tuple(tile.name for tile in tiles), selected, now, width, height)
        if key == self._key:
            return
        self._key = key

        canvas = self._canvas
        canvas.delete("all")
        grid_width = COLUMNS * TILE_WIDTH + (COLUMNS - 1) * GAP
        left = (width - grid_width) // 2
        right = left + grid_width

        canvas.create_oval(left, 36, left + 40, 76, fill=LOGO_GREEN, outline="")
        canvas.create_text(left + 20, 56, text="X", fill=TEXT, font=(FONT, 18, "bold"))
        canvas.create_text(left + 56, 56, text="Xbox mode", anchor="w", fill=TEXT, font=(FONT, 26, "bold"))
        draw_status(canvas, right, 56, now)

        if not tiles:
            canvas.create_text(width // 2, height // 2, text="אין אפליקציות להצגה", fill=MUTED, font=(FONT, 24))
            return

        visible_rows = max(1, (height - TOP - FOOTER) // (TILE_HEIGHT + GAP))
        selected_row = selected // COLUMNS
        first_row = 0 if selected_row < visible_rows else selected_row - visible_rows + 1

        for index, tile in enumerate(tiles):
            row, column = divmod(index, COLUMNS)
            if row < first_row or row >= first_row + visible_rows:
                continue
            x1 = left + column * (TILE_WIDTH + GAP)
            y1 = TOP + (row - first_row) * (TILE_HEIGHT + GAP)
            x2, y2 = x1 + TILE_WIDTH, y1 + TILE_HEIGHT
            if tile.selected:
                rounded(canvas, x1 - 5, y1 - 5, x2 + 5, y2 + 5, 24, fill=FOCUS_RING, outline="")
            rounded(canvas, x1, y1, x2, y2, 18, fill=TILE_FOCUSED if tile.selected else TILE, outline="")
            avatar = AVATARS[sum(map(ord, tile.name)) % len(AVATARS)]
            canvas.create_oval(x1 + 24, y1 + 24, x1 + 84, y1 + 84, fill=avatar, outline="")
            canvas.create_text(x1 + 54, y1 + 54, text=tile.name[:1].upper(), fill="#ffffff", font=(FONT, 24, "bold"))
            canvas.create_text(
                x1 + 24, y2 - 24, text=tile.name, anchor="sw", width=TILE_WIDTH - 48, fill=TEXT, font=(FONT, 17, "bold")
            )

        canvas.create_text(
            left,
            height - FOOTER // 2,
            text="D-pad ניווט      A פתיחה      B סגירה",
            anchor="w",
            fill=MUTED,
            font=(FONT, 16),
        )
