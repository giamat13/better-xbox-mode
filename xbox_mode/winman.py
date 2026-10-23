"""Window enumeration, focus and close helpers (Win32 via ctypes)."""
import ctypes
import ctypes.wintypes as wt
import os
from dataclasses import dataclass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
IGNORED_TITLES = {"Program Manager", "Windows Input Experience", "Microsoft Text Input Application"}


@dataclass
class Win:
    hwnd: int
    title: str
    exe: str
    path: str = ""


def _exe_path(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wt.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(h)
    return ""


def list_windows(exclude=()):
    found = []

    @WNDENUMPROC
    def cb(hwnd, _):
        if hwnd in exclude or not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:  # WS_EX_TOOLWINDOW
            return True
        cloaked = wt.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value in IGNORED_TITLES:
            return True
        path = _exe_path(hwnd)
        found.append(Win(hwnd, buf.value, os.path.basename(path), path))
        return True

    user32.EnumWindows(cb, 0)
    return found


def foreground():
    return user32.GetForegroundWindow() or 0


def focus(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # A synthetic Alt press lets SetForegroundWindow succeed from a background process.
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)


def close(hwnd):
    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE


SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def is_fullscreen(hwnd):
    """True for a captionless window covering the screen (a game); a maximized app has a caption."""
    if not hwnd:
        return False
    if user32.GetWindowLongW(hwnd, -16) & 0x00C00000 == 0x00C00000:  # WS_CAPTION
        return False
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, cls, 64)
    if cls.value in SHELL_CLASSES:
        return False
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left <= 0 and r.top <= 0
            and r.right >= user32.GetSystemMetrics(0)
            and r.bottom >= user32.GetSystemMetrics(1))


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _tray_windows():
    out = []
    for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        h = user32.FindWindowW(cls, None)
        if h:
            out.append(h)
    return out


def set_taskbar_visible(visible):
    for h in _tray_windows():
        user32.ShowWindow(h, 5 if visible else 0)
