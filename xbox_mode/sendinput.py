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


# Keys the hardware reports as "extended": without the flag the arrows, Home/End/Page keys and Win read as numpad keys.
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C}


def send_combo(vks):
    """Presses the keys in order and releases them in reverse, like holding Ctrl and tapping C."""
    for vk in vks:
        _send(vk=vk, flags=0x0001 if vk in EXTENDED else 0)
    for vk in reversed(vks):
        _send(vk=vk, flags=0x0002 | (0x0001 if vk in EXTENDED else 0))


def vk_for_char(ch):
    """The virtual-key code that types a character on the current layout, or None."""
    code = user32.VkKeyScanW(ord(ch))
    return None if code == -1 else code & 0xFF


def send_text(text):
    # KEYEVENTF_UNICODE types the character itself, independent of the active keyboard layout.
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        _send(scan=unit, flags=0x0004)
        _send(scan=unit, flags=0x0004 | 0x0002)
