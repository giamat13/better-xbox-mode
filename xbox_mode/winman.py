"""Window enumeration, focus, close and full-screen helpers (Win32 via ctypes)."""
import ctypes
import ctypes.wintypes as wt
import os
from dataclasses import dataclass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
psapi = ctypes.windll.psapi
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]

user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.IsZoomed.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
IGNORED_TITLES = {"Program Manager", "Windows Input Experience", "Microsoft Text Input Application"}
# Windows that must never be forced to full screen: shell surfaces, dialogs and Store/UWP frames.
NO_FULLSCREEN_CLASSES = {"ApplicationFrameWindow", "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                         "#32770"}
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000


@dataclass
class Win:
    hwnd: int
    title: str
    exe: str
    path: str = ""


def exe_path(hwnd):
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


def pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def module_names(pid):
    """Lower-cased names of the DLLs loaded in a process, or None when it cannot be inspected."""
    h = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
    if not h:
        return None
    try:
        modules = (wt.HMODULE * 1024)()
        needed = wt.DWORD()
        if not psapi.EnumProcessModulesEx(h, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3):  # LIST_MODULES_ALL
            return None
        name = ctypes.create_unicode_buffer(260)
        found = set()
        for i in range(min(needed.value // ctypes.sizeof(wt.HMODULE), len(modules))):
            if psapi.GetModuleBaseNameW(h, modules[i], name, 260):
                found.add(name.value.lower())
        return found
    finally:
        kernel32.CloseHandle(h)


def exe_name(hwnd):
    return os.path.basename(exe_path(hwnd)) if hwnd else ""


def title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


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
        path = exe_path(hwnd)
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


def minimize(hwnd):
    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE


def close(hwnd):
    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.MonitorFromWindow.restype = wt.HANDLE
user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(_MonitorInfo)]


def window_rect(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def monitor_rect(hwnd):
    """The full area of the monitor the window is on (not just the primary one)."""
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    if user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):  # MONITOR_DEFAULTTONEAREST
        m = info.rcMonitor
        return m.left, m.top, m.right, m.bottom
    return (0, 0) + screen_size()


def covers(rect, monitor):
    return rect[0] <= monitor[0] and rect[1] <= monitor[1] and rect[2] >= monitor[2] and rect[3] >= monitor[3]


def covers_screen(hwnd):
    return covers(window_rect(hwnd), monitor_rect(hwnd))


def fullscreen_plan(cls, style, rect, monitor):
    """Decides how to make a window borderless and monitor-sized, like F11: (new style, (x, y, w, h)), or None to
    leave it alone. Windows that are already full screen without a title bar are never touched, and nothing is ever
    restored or shrunk: apps read that as a request to leave their own full-screen mode."""
    if cls in NO_FULLSCREEN_CLASSES or not style & WS_THICKFRAME:
        return None
    if rect[2] - rect[0] < 400 or rect[3] - rect[1] < 300:
        return None
    if covers(rect, monitor) and style & WS_CAPTION != WS_CAPTION:
        return None
    return style & ~(WS_CAPTION | WS_THICKFRAME), (monitor[0], monitor[1], monitor[2] - monitor[0], monitor[3] - monitor[1])


def fullscreenize(hwnd):
    """Applies fullscreen_plan to a window. Returns True if it changed anything."""
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, cls, 64)
    style = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    plan = fullscreen_plan(cls.value, style, window_rect(hwnd), monitor_rect(hwnd))
    if plan is None:
        return False
    new_style, (x, y, w, h) = plan
    user32.SetWindowLongW(hwnd, -16, ctypes.c_long(new_style).value)
    user32.SetWindowPos(hwnd, None, x, y, w, h, 0x0004 | 0x0010 | 0x0020)  # NOZORDER | NOACTIVATE | FRAMECHANGED
    return True


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
