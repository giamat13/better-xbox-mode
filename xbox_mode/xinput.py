"""XInput polling via ctypes, with edge detection and auto-repeat navigation."""
import ctypes
import ctypes.wintypes as wt

BUTTON_BITS = {
    "up": 0x0001, "down": 0x0002, "left": 0x0004, "right": 0x0008,
    "start": 0x0010, "back": 0x0020, "ls": 0x0040, "rs": 0x0080,
    "lb": 0x0100, "rb": 0x0200, "guide": 0x0400,
    "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000,
}
DIRECTIONS = ("up", "down", "left", "right")
REPEAT_DELAY = 0.40
REPEAT_RATE = 0.11
STICK_NAV_THRESHOLD = 0.55


class _Gamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", wt.WORD), ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wt.DWORD), ("Gamepad", _Gamepad)]


class _Battery(ctypes.Structure):
    _fields_ = [("BatteryType", ctypes.c_ubyte), ("BatteryLevel", ctypes.c_ubyte)]


BATTERY_WIRED, BATTERY_EMPTY, BATTERY_LOW = 1, 0, 1
BATTERY_CHECK_SECONDS = 30.0


def _load_getter():
    """Returns (state getter, battery getter); either may be None."""
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(name)
        except OSError:
            continue
        battery = None
        try:
            battery = dll.XInputGetBatteryInformation
            battery.argtypes = [wt.DWORD, ctypes.c_ubyte, ctypes.POINTER(_Battery)]
            battery.restype = wt.DWORD
        except AttributeError:
            battery = None
        # Ordinal 100 is XInputGetStateEx, the only variant that reports the Guide button.
        for key in (100, "XInputGetState"):
            try:
                fn = dll[key]
            except (AttributeError, KeyError):
                continue
            fn.argtypes = [wt.DWORD, ctypes.POINTER(_State)]
            fn.restype = wt.DWORD
            return fn, battery
    return None, None


class Pad:
    def __init__(self):
        self._get, self._get_battery = _load_getter()
        self.connected = False
        self.battery = None  # None (unknown or wired), or "empty", "low", "medium", "full"
        self._next_battery = 0.0
        self.stick_nav = True  # left stick also produces direction events (off while it drives the mouse)
        self.held = set()
        self.pressed = set()
        self.released = set()
        self.nav = []
        self.lx = self.ly = self.rx = self.ry = 0.0
        self.lt = self.rt = 0.0
        self._next_repeat = {}
        self._slot = 0

    @staticmethod
    def _norm(v, dead=0.18):
        f = max(-1.0, v / 32767.0)
        if abs(f) < dead:
            return 0.0
        return (abs(f) - dead) / (1 - dead) * (1 if f > 0 else -1)

    def _read(self):
        if not self._get:
            return None
        state = _State()
        slots = [self._slot] + [i for i in range(4) if i != self._slot]
        for i in slots:
            if self._get(i, ctypes.byref(state)) == 0:
                self._slot = i
                return state.Gamepad
        return None

    def _read_battery(self, now):
        """The pad's battery level, checked every so often. None for wired pads and when it cannot be read."""
        if now < self._next_battery:
            return
        self._next_battery = now + BATTERY_CHECK_SECONDS
        if not (self._get_battery and self.connected):
            self.battery = None
            return
        info = _Battery()
        if self._get_battery(self._slot, 0, ctypes.byref(info)) != 0 or info.BatteryType == BATTERY_WIRED                 or info.BatteryType == 0:
            self.battery = None
            return
        self.battery = ("empty", "low", "medium", "full")[min(info.BatteryLevel, 3)]

    def update(self, now):
        gp = self._read()
        self.connected = gp is not None
        self._read_battery(now)
        bits = gp.wButtons if gp else 0
        held = {n for n, b in BUTTON_BITS.items() if bits & b}
        if gp:
            self.lx, self.ly = self._norm(gp.sThumbLX), self._norm(gp.sThumbLY)
            self.rx, self.ry = self._norm(gp.sThumbRX), self._norm(gp.sThumbRY)
            self.lt, self.rt = gp.bLeftTrigger / 255.0, gp.bRightTrigger / 255.0
        else:
            self.lx = self.ly = self.rx = self.ry = self.lt = self.rt = 0.0
        self.pressed = held - self.held
        self.released = self.held - held
        self.held = held

        dirs = {d for d in DIRECTIONS if d in held}
        if self.stick_nav:
            if self.ly > STICK_NAV_THRESHOLD: dirs.add("up")
            if self.ly < -STICK_NAV_THRESHOLD: dirs.add("down")
            if self.lx < -STICK_NAV_THRESHOLD: dirs.add("left")
            if self.lx > STICK_NAV_THRESHOLD: dirs.add("right")

        self.nav = []
        for d in dirs:
            due = self._next_repeat.get(d)
            if due is None:
                self.nav.append(d)
                self._next_repeat[d] = now + REPEAT_DELAY
            elif now >= due:
                self.nav.append(d)
                self._next_repeat[d] = now + REPEAT_RATE
        for d in list(self._next_repeat):
            if d not in dirs:
                del self._next_repeat[d]

    def events(self):
        """Discrete button events for UI navigation (repeating directions, one-shot buttons)."""
        return self.nav + [b for b in sorted(self.pressed) if b not in DIRECTIONS]
