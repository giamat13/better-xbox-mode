"""Hides the Windows taskbar while Xbox mode runs and restores it on exit. Nothing else in Windows changes."""
import atexit
import ctypes
import sys

SW_HIDE = 0
SW_SHOW = 5
TASKBAR_CLASSES = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")


def _user32():
    user32 = ctypes.WinDLL("user32")
    user32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowExW.restype = ctypes.c_void_p
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    return user32


def taskbar_handles():
    user32 = _user32()
    handles = []
    for name in TASKBAR_CLASSES:
        hwnd = None
        while True:
            hwnd = user32.FindWindowExW(None, hwnd, name, None)
            if not hwnd:
                break
            handles.append(hwnd)
    return handles


def show_all_taskbars() -> None:
    """Bring every taskbar back. Used by --show-taskbar after the app was killed with the taskbar hidden."""
    if sys.platform != "win32":
        return
    user32 = _user32()
    for hwnd in taskbar_handles():
        user32.ShowWindow(hwnd, SW_SHOW)


class Taskbar:
    def __init__(self) -> None:
        self._hidden_handles = []
        atexit.register(self.restore)

    def hide(self) -> None:
        if sys.platform != "win32" or self._hidden_handles:
            return
        user32 = _user32()
        for hwnd in taskbar_handles():
            user32.ShowWindow(hwnd, SW_HIDE)
            self._hidden_handles.append(hwnd)

    def restore(self) -> None:
        if sys.platform != "win32" or not self._hidden_handles:
            return
        user32 = _user32()
        for hwnd in self._hidden_handles:
            user32.ShowWindow(hwnd, SW_SHOW)
        self._hidden_handles = []
