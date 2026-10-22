"""Drawing helpers and window flags shared by the launcher and the on-screen keyboard."""
import ctypes
import sys

BACKGROUND = "#0b0f14"
TEXT = "#ffffff"
MUTED = "#9aa4af"
FONT = "Segoe UI"

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
GA_ROOT = 2
SW_SHOWNOACTIVATE = 4


def rounded(canvas, x1, y1, x2, y2, radius, **options):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **options)


def draw_status(canvas, width: int, y: int, time_text: str) -> None:
    """Clock and Wi-Fi, volume and battery glyphs in the top-right corner, like the Xbox home bar."""
    canvas.create_text(width - 40, y, text=time_text, anchor="e", fill=TEXT, font=(FONT, 22, "bold"))
    x = width - 340
    canvas.create_arc(x, y - 12, x + 24, y + 12, start=45, extent=90, style="arc", outline=TEXT, width=2)
    canvas.create_arc(x + 4, y - 7, x + 20, y + 9, start=45, extent=90, style="arc", outline=TEXT, width=2)
    canvas.create_polygon(x + 42, y - 6, x + 50, y - 6, x + 58, y - 12, x + 58, y + 12, x + 50, y + 6, x + 42, y + 6,
                          fill=TEXT, outline="")
    battery = x + 84
    canvas.create_rectangle(battery, y - 8, battery + 30, y + 8, outline=TEXT, width=2)
    canvas.create_rectangle(battery + 30, y - 4, battery + 34, y + 4, fill=TEXT, outline="")
    canvas.create_rectangle(battery + 3, y - 5, battery + 24, y + 5, fill=TEXT, outline="")


def show_without_activating(window) -> None:
    """Show a Tk window without making it the foreground window, so typed keys reach the app underneath."""
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32")
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    hwnd = user32.GetAncestor(window.winfo_id(), GA_ROOT)
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
