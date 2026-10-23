"""GDI helpers: live window thumbnails (PrintWindow) and window/exe icons as pygame surfaces."""
import ctypes
import ctypes.wintypes as wt

import pygame

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32


class _BmiHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class _Bmi(ctypes.Structure):
    _fields_ = [("bmiHeader", _BmiHeader), ("bmiColors", wt.DWORD * 3)]


user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.DrawIconEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, wt.HICON, ctypes.c_int, ctypes.c_int,
                              wt.UINT, wt.HBRUSH, wt.UINT]
user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
                                       ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
user32.GetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetClassLongPtrW.restype = ctypes.c_size_t
user32.DestroyIcon.argtypes = [wt.HICON]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(_Bmi), wt.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
shell32.ExtractIconExW.argtypes = [wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.HICON),
                                   ctypes.POINTER(wt.HICON), wt.UINT]


class _Dib:
    """A top-down 32-bit DIB selected into a memory DC."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        screen = user32.GetDC(None)
        self.dc = gdi32.CreateCompatibleDC(screen)
        user32.ReleaseDC(None, screen)
        bmi = _Bmi()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BmiHeader)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        self.ptr = ctypes.c_void_p()
        self.bmp = gdi32.CreateDIBSection(self.dc, ctypes.byref(bmi), 0, ctypes.byref(self.ptr), None, 0)
        self.old = gdi32.SelectObject(self.dc, self.bmp)

    def fill(self, value):
        ctypes.memset(self.ptr, value, self.w * self.h * 4)

    def data(self):
        return ctypes.string_at(self.ptr, self.w * self.h * 4)

    def close(self):
        gdi32.SelectObject(self.dc, self.old)
        gdi32.DeleteObject(self.bmp)
        gdi32.DeleteDC(self.dc)


def capture_window(hwnd, max_w=800):
    """Returns a pygame surface with the window's current contents, or None (minimized/unreadable)."""
    if user32.IsIconic(hwnd):
        return None
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0 or w * h > 8000 * 4500:
        return None
    dib = _Dib(w, h)
    try:
        dib.fill(0)
        user32.PrintWindow(hwnd, dib.dc, 2)  # PW_RENDERFULLCONTENT
        raw = dib.data()
    finally:
        dib.close()
    buf = bytearray(raw)
    buf[0::4], buf[2::4] = raw[2::4], raw[0::4]  # BGRA -> RGBA
    buf[3::4] = b"\xff" * (w * h)
    surf = pygame.image.frombuffer(bytes(buf), (w, h), "RGBA").convert()
    if w > max_w:
        surf = pygame.transform.smoothscale(surf, (max_w, max(1, h * max_w // w)))
    return surf


def _draw_icon(hicon, size, fill):
    dib = _Dib(size, size)
    try:
        dib.fill(fill)
        user32.DrawIconEx(dib.dc, 0, 0, hicon, size, size, 0, None, 3)
        return dib.data()
    finally:
        dib.close()


def icon_surface(hicon, size=32):
    # Render over black and over white to recover per-pixel alpha.
    black, white = _draw_icon(hicon, size, 0x00), _draw_icon(hicon, size, 0xFF)
    out = bytearray(size * size * 4)
    for o in range(0, size * size * 4, 4):
        a = 255 - (white[o + 1] - black[o + 1])
        if a <= 0:
            continue
        out[o] = min(255, black[o + 2] * 255 // a)
        out[o + 1] = min(255, black[o + 1] * 255 // a)
        out[o + 2] = min(255, black[o] * 255 // a)
        out[o + 3] = min(255, a)
    return pygame.image.frombuffer(bytes(out), (size, size), "RGBA").convert_alpha()


def window_icon(hwnd, exe_path, size=32):
    """Icon of a window: the icon it advertises, else its class icon, else the exe's own icon."""
    result = ctypes.c_size_t(0)
    user32.SendMessageTimeoutW(hwnd, 0x007F, 1, 0, 2, 100, ctypes.byref(result))  # WM_GETICON, ICON_BIG
    hicon = result.value or user32.GetClassLongPtrW(hwnd, -14)
    owned = False
    if not hicon and exe_path and not exe_path.lower().endswith("applicationframehost.exe"):
        large = wt.HICON()
        if shell32.ExtractIconExW(exe_path, 0, ctypes.byref(large), None, 1) and large:
            hicon, owned = large.value, True
    if not hicon:
        return None
    try:
        return icon_surface(hicon, size)
    finally:
        if owned:
            user32.DestroyIcon(hicon)
