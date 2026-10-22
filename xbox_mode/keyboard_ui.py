"""Bottom-docked on-screen keyboard for the controller. It never takes focus, so text goes to the app underneath."""
from .keyboard_model import OnScreenKeyboard
from .ui_common import BACKGROUND, FONT, MUTED, TEXT, rounded, show_without_activating

KEY = "#1f2832"
KEY_SELECTED = "#107c10"
HEIGHT = 390
KEY_WIDTH = 88
KEY_HEIGHT = 58
KEY_GAP = 8
ROW_GAP = 10
CONTROL_WIDTHS = (140, 520, 140, 170)  # lang, space, backspace, enter
HINT = "D-pad ניווט      A הקלדה      X מחיקה      START Enter      B / Y סגירה"


class KeyboardView:
    def __init__(self, root) -> None:
        import tkinter as tk

        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(bg=BACKGROUND)
        self._canvas = tk.Canvas(self._window, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._shown = False
        self._key = None

    def sync(self, on_screen: OnScreenKeyboard) -> None:
        if on_screen.open and not self._shown:
            self._show()
        elif not on_screen.open and self._shown:
            self._window.withdraw()
            self._shown = False
        if self._shown:
            self._render(on_screen)

    def _show(self) -> None:
        screen_width = self._window.winfo_screenwidth()
        screen_height = self._window.winfo_screenheight()
        self._window.geometry(f"{screen_width}x{HEIGHT}+0+{screen_height - HEIGHT}")
        self._window.deiconify()
        self._window.update_idletasks()
        show_without_activating(self._window)
        self._shown = True
        self._key = None

    def _render(self, on_screen: OnScreenKeyboard) -> None:
        width = self._canvas.winfo_width()
        selection = on_screen.selection()
        key = (on_screen.language, selection, width)
        if key == self._key:
            return
        self._key = key

        canvas = self._canvas
        canvas.delete("all")
        rows = on_screen.rows()
        last = len(rows) - 1
        for row_index, row in enumerate(rows):
            widths = CONTROL_WIDTHS if row_index == last else [KEY_WIDTH] * len(row)
            total = sum(widths) + KEY_GAP * (len(row) - 1)
            x = (width - total) // 2
            y = 14 + row_index * (KEY_HEIGHT + ROW_GAP)
            for column_index, (item, item_width) in enumerate(zip(row, widths)):
                fill = KEY_SELECTED if (row_index, column_index) == selection else KEY
                rounded(canvas, x, y, x + item_width, y + KEY_HEIGHT, 12, fill=fill, outline="")
                canvas.create_text(
                    x + item_width // 2,
                    y + KEY_HEIGHT // 2,
                    text=item.label,
                    fill=TEXT,
                    font=(FONT, 20, "bold"),
                )
                x += item_width + KEY_GAP
        canvas.create_text(width // 2, HEIGHT - 22, text=HINT, fill=MUTED, font=(FONT, 15))
