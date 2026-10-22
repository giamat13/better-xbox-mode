"""Windows process probes and the on-screen keyboard. Non-Windows branches return empty results."""
import ctypes
import logging
import os
import subprocess
import sys
from ctypes import wintypes
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE = ctypes.c_void_p(-1).value


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


def _windows_api():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return user32, kernel32


def foreground_process() -> Tuple[Optional[int], Optional[str]]:
    """Return (pid, lowercase exe name) of the window that has focus."""
    if sys.platform != "win32":
        return None, None
    user32, kernel32 = _windows_api()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return pid.value, None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return pid.value, os.path.basename(buffer.value).lower()
        return pid.value, None
    finally:
        kernel32.CloseHandle(handle)


def list_modules(pid: int) -> List[str]:
    """Return the lowercase base names of every DLL loaded in the process."""
    if sys.platform != "win32":
        return _linux_modules(pid)
    _, kernel32 = _windows_api()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if not snapshot or snapshot == INVALID_HANDLE:
        return []
    names: List[str] = []
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            names.append(entry.szModule.lower())
            ok = kernel32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def _linux_modules(pid: int) -> List[str]:
    try:
        with open(f"/proc/{pid}/maps", encoding="utf-8", errors="replace") as maps:
            lines = maps.read().splitlines()
    except OSError:
        return []
    names = set()
    for line in lines:
        parts = line.split(maxsplit=5)
        if len(parts) == 6 and parts[5].startswith("/"):
            names.add(os.path.basename(parts[5]).lower())
    return sorted(names)


def osk_running() -> bool:
    if sys.platform != "win32":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq osk.exe", "/NH"], capture_output=True, text=True, check=False
    )
    return "osk.exe" in result.stdout.lower()


def toggle_osk() -> None:
    """Open the Windows On-Screen Keyboard, or close it if it is already open."""
    if sys.platform != "win32":
        log.info("on-screen keyboard is only available on Windows")
        return
    if osk_running():
        subprocess.run(["taskkill", "/IM", "osk.exe", "/F"], capture_output=True, check=False)
    else:
        _start_osk()


def _start_osk() -> None:
    try:
        subprocess.Popen(["osk.exe"])
    except OSError:
        # Some Windows images refuse CreateProcess for osk.exe (WinError 740, elevation manifest).
        # ShellExecute goes through the shell and is accepted in that case.
        os.startfile("osk.exe")  # type: ignore[attr-defined]  # Windows only
