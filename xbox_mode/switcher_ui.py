"""Full-screen task switcher drawn like the Xbox mode switcher: running apps on top, a focused card in the middle."""
import datetime
from typing import Optional, Tuple

from .switcher import TaskSwitcher
from .ui_common import BACKGROUND, FONT, MUTED, TEXT, draw_status, rounded

CARD_FOCUS = "#4fc3f7"
CARD = "#151a20"
CARD_TITLE = "#0b0f14"
CARD_SIDE = "#11161c"
ICON = "#1f2832"
ICON_SELECTED = "#2b3642"
AVATARS = ("#107c10", "#0078d4", "#8764b8", "#ca5010", "#038387", "#c239b3")
CARD_WIDTH = 640
CARD_HEIGHT = 380
TOP_ROW = 46
HINT_ROW = -1  # computed from the canvas height


class SwitcherView:
    def __init__(self, root) -> None:
        import tkinter as tk

        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.title("Xbox mode switcher")
        self._window.configure(bg=BACKGROUND)
        self._canvas = tk.Canvas(self._window, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._visible = False
        self._key: Optional[Tuple] = None

    def sync(self, switcher: TaskSwitcher) -> None:
        if switcher.open and not self._visible:
            self._window.deiconify()
            self._window.attributes("-fullscreen", True)
            self._key = None
            self._visible = True
        elif not switcher.open and self._visible:
            self._window.withdraw()
            self._visible = False
        if self._visible:
            self._render(switcher)

    def _render(self, switcher: TaskSwitcher) -> None:
        items = switcher.items
        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()
        now = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        key = (tuple(item.hwnd for item in items), switcher.index, now, width, height)
        if key == self._key:
            return
        self._key = key

        canvas = self._canvas
        canvas.delete("all")
        draw_status(canvas, width, TOP_ROW, now)

        if not items:
            canvas.create_text(width // 2, height // 2, text="אין חלונות פתוחים", fill=MUTED, font=(FONT, 26))
            self._draw_hints(width, height, has_items=False)
            return

        self._draw_top_row(items, switcher.index, width)
        selected = items[switcher.index]
        left = (width - CARD_WIDTH) // 2
        top = (height - CARD_HEIGHT) // 2 - 10
        neighbour = items[switcher.index + 1] if switcher.index + 1 < len(items) else None
        if neighbour is not None:
            rounded(canvas, left + CARD_WIDTH + 40, top + 40, left + CARD_WIDTH + 340, top + CARD_HEIGHT - 40, 18,
                    fill=CARD_SIDE, outline="")
            canvas.create_text(left + CARD_WIDTH + 70, top + 70, text=neighbour.title[:28], anchor="w",
                               fill=MUTED, font=(FONT, 16, "bold"))

        rounded(canvas, left - 4, top - 4, left + CARD_WIDTH + 4, top + CARD_HEIGHT + 4, 22, fill=CARD_FOCUS, outline="")
        rounded(canvas, left, top, left + CARD_WIDTH, top + CARD_HEIGHT, 18, fill=CARD, outline="")
        rounded(canvas, left, top, left + CARD_WIDTH, top + 56, 18, fill=CARD_TITLE, outline="")
        canvas.create_rectangle(left, top + 40, left + CARD_WIDTH, top + 56, fill=CARD_TITLE, outline="")
        avatar = AVATARS[sum(map(ord, selected.title)) % len(AVATARS)]
        canvas.create_oval(left + 18, top + 12, left + 46, top + 40, fill=avatar, outline="")
        canvas.create_text(left + 32, top + 26, text=selected.title[:1].upper() or "?", fill=TEXT,
                           font=(FONT, 12, "bold"))
        canvas.create_text(left + 60, top + 28, text=selected.title, anchor="w", fill=TEXT,
                           font=(FONT, 18, "bold"), width=CARD_WIDTH - 90)
        canvas.create_text(left + CARD_WIDTH // 2, top + 56 + (CARD_HEIGHT - 56) // 2, text=selected.title[:1].upper(),
                           fill=avatar, font=(FONT, 120, "bold"))

        self._draw_hints(width, height, has_items=True)

    def _draw_top_row(self, items, selected_index: int, width: int) -> None:
        canvas = self._canvas
        size = 56
        gap = 14
        total = len(items) * size + (len(items) - 1) * gap
        x = (width - total) // 2
        y = 110
        canvas.create_text(x - 40, y + size // 2, text="LB", fill=MUTED, font=(FONT, 14, "bold"))
        canvas.create_text(x + total + 40, y + size // 2, text="RB", fill=MUTED, font=(FONT, 14, "bold"))
        for index, item in enumerate(items):
            fill = ICON_SELECTED if index == selected_index else ICON
            rounded(canvas, x, y, x + size, y + size, 12, fill=fill, outline=CARD_FOCUS if index == selected_index else "")
            avatar = AVATARS[sum(map(ord, item.title)) % len(AVATARS)]
            canvas.create_oval(x + 10, y + 10, x + size - 10, y + size - 10, fill=avatar, outline="")
            canvas.create_text(x + size // 2, y + size // 2, text=item.title[:1].upper() or "?", fill=TEXT,
                               font=(FONT, 14, "bold"))
            x += size + gap

    def _draw_hints(self, width: int, height: int, has_items: bool) -> None:
        canvas = self._canvas
        y = height - 64
        hints = [("A", "בחר")]
        if has_items:
            hints.append(("X", "סגור אפליקציה"))
        hints.append(("B", "חזרה"))
        x = 60
        for letter, label in hints:
            canvas.create_oval(x, y - 14, x + 28, y + 14, outline=TEXT, width=2)
            canvas.create_text(x + 14, y, text=letter, fill=TEXT, font=(FONT, 13, "bold"))
            canvas.create_text(x + 40, y, text=label, anchor="w", fill=TEXT, font=(FONT, 16))
            x += 260
        dock_y = height - 26
        canvas.create_line(0, dock_y - 22, width, dock_y - 22, fill=ICON)
        canvas.create_text(width // 2 - 150, dock_y, text="Xbox mode", fill=TEXT, font=(FONT, 15, "bold"))
        canvas.create_text(width // 2 + 150, dock_y, text="שולחן עבודה של Windows", fill=MUTED, font=(FONT, 15))
