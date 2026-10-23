"""Keyboard injection via SendInput."""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32


class _KeyInput(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyInput), ("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _InputUnion)]


def _send(vk=0, scan=0, flags=0):
    inp = _Input(1, _InputUnion(ki=_KeyInput(vk, scan, flags, 0, 0)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_Input))


def send_vk(vk):
    _send(vk=vk)
    _send(vk=vk, flags=0x0002)  # KEYEVENTF_KEYUP


def send_text(text):
    # KEYEVENTF_UNICODE types the character itself, independent of the active keyboard layout.
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        _send(scan=unit, flags=0x0004)
        _send(scan=unit, flags=0x0004 | 0x0002)
