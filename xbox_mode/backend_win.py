"""Windows output through SendInput. Keys go out as scan codes, which DirectInput games also read."""
import ctypes

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

# name -> (scan code, needs extended flag)
SCANCODES = {
    "enter": (0x1C, False),
    "escape": (0x01, False),
    "backspace": (0x0E, False),
    "tab": (0x0F, False),
    "space": (0x39, False),
    "up": (0x48, True),
    "down": (0x50, True),
    "left": (0x4B, True),
    "right": (0x4D, True),
    "pageup": (0x49, True),
    "pagedown": (0x51, True),
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_int32),
        ("dy", ctypes.c_int32),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_uint32), ("wParamL", ctypes.c_uint16), ("wParamH", ctypes.c_uint16)]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_uint32), ("u", _InputUnion)]


def _mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_MOUSE
    item.mi = MOUSEINPUT(dx, dy, ctypes.c_uint32(data).value, flags, 0, 0)
    return item


def _key_input(name: str, down: bool) -> INPUT:
    scan, extended = SCANCODES[name]
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if not down:
        flags |= KEYEVENTF_KEYUP
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.ki = KEYBDINPUT(0, scan, flags, 0, 0)
    return item


class WinInputBackend:
    def __init__(self) -> None:
        self._send_input = ctypes.windll.user32.SendInput
        self._send_input.argtypes = [ctypes.c_uint32, ctypes.POINTER(INPUT), ctypes.c_int]
        self._send_input.restype = ctypes.c_uint32

    def _send(self, *items: INPUT) -> None:
        array = (INPUT * len(items))(*items)
        sent = self._send_input(len(items), array, ctypes.sizeof(INPUT))
        if sent != len(items):
            raise ctypes.WinError(ctypes.get_last_error())

    def move_relative(self, dx: int, dy: int) -> None:
        self._send(_mouse_input(MOUSEEVENTF_MOVE, dx, dy))

    def button(self, name: str, down: bool) -> None:
        down_flag, up_flag = BUTTON_FLAGS[name]
        self._send(_mouse_input(down_flag if down else up_flag))

    def wheel(self, ticks: int) -> None:
        self._send(_mouse_input(MOUSEEVENTF_WHEEL, data=ticks * 120))

    def key(self, name: str, down: bool) -> None:
        self._send(_key_input(name, down))
