"""Controller-as-desktop-input: stick moves the cursor, buttons click and press keys, triggers zoom the screen."""
import ctypes
import ctypes.wintypes as wt
import math
import threading

from . import winman

user32 = ctypes.windll.user32

LEFTDOWN, LEFTUP, RIGHTDOWN, RIGHTUP, WHEEL, HWHEEL = 0x0002, 0x0004, 0x0008, 0x0010, 0x0800, 0x1000
VK_CONTROL, VK_LWIN, VK_C, VK_V = 0x11, 0x5B, 0x43, 0x56
CLIPBOARD_SETTLE = 0.15  # seconds between Ctrl+C and opening the clipboard history
KEYS = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27}
CURSOR_SPEED = 1400.0  # pixels per second at full deflection
SCROLL_SPEED = 900.0
ZOOM_TRIGGER = 0.5     # how far a trigger must be pulled to count
ZOOM_RATE = 1.3        # natural-log zoom change per second while a trigger is held (about 3.7x per second)
ZOOM_MAX = 10.0
FOLLOW_MARGIN = 0.12   # the cursor may roam this far (fraction of the view) from the edge before the view follows


def _cursor_pos():
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _load_magnification():
    try:
        dll = ctypes.windll.magnification
        dll.MagInitialize.restype = wt.BOOL
        dll.MagUninitialize.restype = wt.BOOL
        dll.MagSetFullscreenTransform.argtypes = [ctypes.c_float, ctypes.c_int, ctypes.c_int]
        dll.MagSetFullscreenTransform.restype = wt.BOOL
        return dll
    except (OSError, AttributeError):
        return None


class Magnifier:
    """Zooms the whole screen through the Windows Magnification API, so there is no Magnifier window to show or close.
    At 100% the API is shut down again and the screen is exactly as it was."""

    def __init__(self, api=None, screen=_screen_size, cursor=_cursor_pos):
        self._api = api
        self._tried = api is not None
        self._screen = screen
        self._cursor = cursor
        self.level = 1.0
        self._on = False
        self._ox = self._oy = 0.0

    def _dll(self):
        if not self._tried:
            self._tried = True
            self._api = _load_magnification()
        return self._api

    def zoom(self, direction, dt):
        """direction: +1 in, -1 out, 0 none."""
        if not direction or not self._dll():
            return
        level = min(ZOOM_MAX, self.level * math.exp(direction * ZOOM_RATE * dt))
        if level <= 1.0:
            self.reset()
            return
        if not self._on:
            self._api.MagInitialize()
            self._on = True
            w, h = self._screen()
            cx, cy = self._cursor()
            self._ox, self._oy = cx - w / level / 2, cy - h / level / 2
        self.level = level
        self.follow()

    def follow(self):
        """Keeps the cursor inside the zoomed view, panning only when it gets near an edge."""
        if not self._on:
            return
        w, h = self._screen()
        vw, vh = w / self.level, h / self.level
        cx, cy = self._cursor()
        mx, my = vw * FOLLOW_MARGIN, vh * FOLLOW_MARGIN
        self._ox = min(max(self._ox, cx + mx - vw), cx - mx)
        self._oy = min(max(self._oy, cy + my - vh), cy - my)
        self._ox = min(max(self._ox, 0.0), w - vw)
        self._oy = min(max(self._oy, 0.0), h - vh)
        self._api.MagSetFullscreenTransform(self.level, int(self._ox), int(self._oy))

    def reset(self):
        if self._on:
            self._api.MagSetFullscreenTransform(1.0, 0, 0)
            self._api.MagUninitialize()
            self._on = False
        self.level = 1.0


class MouseMode:
    def __init__(self):
        self._frac_x = self._frac_y = self._frac_scroll = self._frac_hscroll = 0.0
        self.mag = Magnifier()
        self.clipboard_enabled = True  # off while Xbox Mode's own window is on screen

    def close(self):
        self.mag.reset()

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

        self._frac_hscroll += pad.rx * SCROLL_SPEED * dt
        h_notches = int(self._frac_hscroll / 120)
        if h_notches:
            self._frac_hscroll -= h_notches * 120
            user32.mouse_event(HWHEEL, 0, 0, h_notches * 120, 0)

        self._zoom(pad, dt)

        if "lb" in pad.pressed and self.clipboard_enabled:
            self.copy_and_open_clipboard()
        if "rs" in pad.pressed:
            winman.move_cursor_to_next_monitor()  # click the right stick to jump to the other monitor

        for name, down, up in (("a", LEFTDOWN, LEFTUP), ("x", RIGHTDOWN, RIGHTUP)):
            if name in pad.pressed:
                user32.mouse_event(down, 0, 0, 0, 0)
            if name in pad.released:
                user32.mouse_event(up, 0, 0, 0, 0)

        for d in pad.nav:
            self._tap(KEYS[d])
        if "b" in pad.pressed:
            self._tap(0x1B)  # Esc

    def _zoom(self, pad, dt):
        """RT zooms the screen in and LT zooms it out; pulling both puts it back to normal at once."""
        rt, lt = pad.rt > ZOOM_TRIGGER, pad.lt > ZOOM_TRIGGER
        if rt and lt:
            self.mag.reset()
        else:
            self.mag.zoom(int(rt) - int(lt), dt)
            self.mag.follow()

    def copy_and_open_clipboard(self):
        """LB: Ctrl+C, then the Windows clipboard history (Win+V) so the copy can be pasted from there."""
        self._chord(VK_CONTROL, VK_C)
        timer = threading.Timer(CLIPBOARD_SETTLE, self._chord, (VK_LWIN, VK_V))
        timer.daemon = True
        timer.start()

    @staticmethod
    def _chord(modifier, key):
        user32.keybd_event(modifier, 0, 0, 0)
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, 2, 0)
        user32.keybd_event(modifier, 0, 2, 0)

    @staticmethod
    def _tap(vk):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
