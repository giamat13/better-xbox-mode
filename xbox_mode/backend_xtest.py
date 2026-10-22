"""Linux output through the X server's XTEST extension. Used for development and tests under Xvfb."""
from Xlib import X, XK, display
from Xlib.ext import xtest

BUTTON_CODES = {"left": 1, "middle": 2, "right": 3}
KEYSYM_NAMES = {
    "enter": "Return",
    "escape": "Escape",
    "backspace": "BackSpace",
    "tab": "Tab",
    "space": "space",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "pageup": "Prior",
    "pagedown": "Next",
}


class XTestBackend:
    def __init__(self) -> None:
        self._display = display.Display()
        self._root = self._display.screen().root

    def move_relative(self, dx: int, dy: int) -> None:
        pointer = self._root.query_pointer()
        xtest.fake_input(self._display, X.MotionNotify, x=pointer.root_x + dx, y=pointer.root_y + dy)
        self._display.sync()

    def button(self, name: str, down: bool) -> None:
        event = X.ButtonPress if down else X.ButtonRelease
        xtest.fake_input(self._display, event, BUTTON_CODES[name])
        self._display.sync()

    def wheel(self, ticks: int) -> None:
        code = 4 if ticks > 0 else 5
        for _ in range(abs(ticks)):
            xtest.fake_input(self._display, X.ButtonPress, code)
            xtest.fake_input(self._display, X.ButtonRelease, code)
        self._display.sync()

    def key(self, name: str, down: bool) -> None:
        keycode = self._display.keysym_to_keycode(XK.string_to_keysym(KEYSYM_NAMES[name]))
        event = X.KeyPress if down else X.KeyRelease
        xtest.fake_input(self._display, event, keycode)
        self._display.sync()
