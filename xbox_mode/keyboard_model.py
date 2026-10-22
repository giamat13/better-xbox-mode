"""On-screen keyboard state: which key is selected and what pressing it types. No drawing here."""
from dataclasses import dataclass
from typing import List, Optional

LAYOUTS = {
    "en": ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm,."),
    "he": ("1234567890", "/'קראטוןםפ", "שדגכעיחלךף,", "זסבהנמצתץ."),
}
LANGUAGE_LABEL = {"en": "עב", "he": "EN"}
CONTROL_ROW = ("lang", "space", "backspace", "enter")


@dataclass(frozen=True)
class Key:
    label: str
    action: str  # "text", "lang", "space", "backspace", or "enter"
    value: str = ""


class OnScreenKeyboard:
    def __init__(self) -> None:
        self.open = False
        self.language = "en"
        self._row = 0
        self._col = 0

    def rows(self) -> List[List[Key]]:
        letters = [[Key(char, "text", char) for char in row] for row in LAYOUTS[self.language]]
        control = [
            Key(LANGUAGE_LABEL[self.language], "lang"),
            Key("space", "space", " "),
            Key("⌫", "backspace"),
            Key("Enter", "enter"),
        ]
        return letters + [control]

    def toggle(self) -> bool:
        self.open = not self.open
        return self.open

    def close(self) -> None:
        self.open = False

    def selected(self) -> Key:
        rows = self.rows()
        return rows[self._row][self._col]

    def selection(self) -> tuple:
        return self._row, self._col

    def move(self, dx: int, dy: int) -> None:
        rows = self.rows()
        self._row = min(max(self._row + dy, 0), len(rows) - 1)
        row_length = len(rows[self._row])
        self._col = min(max(self._col + dx, 0), row_length - 1)

    def press(self) -> Optional[Key]:
        """Return the pressed key for the engine to type, or None when the press only changed the layout."""
        key = self.selected()
        if key.action == "lang":
            self.language = "he" if self.language == "en" else "en"
            self._row = min(self._row, len(self.rows()) - 1)
            self._col = min(self._col, len(self.rows()[self._row]) - 1)
            return None
        return key
