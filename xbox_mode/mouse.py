"""Controller-as-desktop-input: stick moves the cursor, buttons click and press keys."""
import ctypes

user32 = ctypes.windll.user32

LEFTDOWN, LEFTUP, RIGHTDOWN, RIGHTUP, WHEEL = 0x0002, 0x0004, 0x0008, 0x0010, 0x0800
KEYS = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27}
CURSOR_SPEED = 1400.0  # pixels per second at full deflection
SCROLL_SPEED = 900.0


class MouseMode:
    def __init__(self):
        self._frac_x = self._frac_y = self._frac_scroll = 0.0

    def apply(self, pad, dt):
        self._frac_x += pad.lx * abs(pad.lx) * CURSOR_SPEED * dt
        self._frac_y += -pad.ly * abs(pad.ly) * CURSOR_SPEED * dt
        dx, dy = int(self._frac_x), int(self._frac_y)
        if dx or dy:
            self._frac_x -= dx
            self._frac_y -= dy
            user32.mouse_event(0x0001, dx, dy, 0, 0)  # MOUSEEVENTF_MOVE

        self._frac_scroll += pad.ry * SCROLL_SPEED * dt
        notches = int(self._frac_scroll / 120)
        if notches:
            self._frac_scroll -= notches * 120
            user32.mouse_event(WHEEL, 0, 0, notches * 120, 0)

        for name, down, up in (("a", LEFTDOWN, LEFTUP), ("x", RIGHTDOWN, RIGHTUP)):
            if name in pad.pressed:
                user32.mouse_event(down, 0, 0, 0, 0)
            if name in pad.released:
                user32.mouse_event(up, 0, 0, 0, 0)

        for d in pad.nav:
            self._tap(KEYS[d])
        if "b" in pad.pressed:
            self._tap(0x1B)  # Esc

    @staticmethod
    def _tap(vk):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
