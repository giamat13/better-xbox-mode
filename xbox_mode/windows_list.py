"""Lists the open top-level windows so the controller can switch to them or close them. Windows only."""
import ctypes
import sys
from ctypes import wintypes
from typing import Iterable, List, NamedTuple

SKIPPED_TITLES = frozenset({"Program Manager", "Windows Input Experience", "Settings", "Xbox mode"})
SKIPPED_CLASSES = frozenset({"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW", "Windows.UI.Core.CoreWindow"})
WM_CLOSE = 0x0010
SW_RESTORE = 9
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class WindowEntry(NamedTuple):
    hwnd: int
    title: str
    class_name: str


def filter_windows(entries: Iterable[WindowEntry], own_title: str = "Xbox mode") -> List[WindowEntry]:
    """Keep windows a person would switch to. Pure function, so it can be tested without Windows."""
    kept = []
    for entry in entries:
        if not entry.title or entry.title in SKIPPED_TITLES or entry.title == own_title:
            continue
        if entry.class_name in SKIPPED_CLASSES:
            continue
        kept.append(entry)
    return kept


def list_windows() -> List[WindowEntry]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.WinDLL("user32")
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    collected: List[WindowEntry] = []

    def on_window(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        ex_style = user32.GetWindowLongPtrW(hwnd, -20)
        if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        collected.append(WindowEntry(int(hwnd), title.value, name.value))
        return True

    user32.EnumWindows.argtypes = [ENUM_WINDOWS_PROC, wintypes.LPARAM]
    user32.EnumWindows(ENUM_WINDOWS_PROC(on_window), 0)
    return filter_windows(collected)


def bring_to_front(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32")
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def close_window(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32")
    user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

