"""Gamepad-driven on-screen keyboard: a non-activating topmost window that types into the foreground app."""
import ctypes
import ctypes.wintypes as wt
import tkinter as tk
from dataclasses import dataclass

user32 = ctypes.windll.user32
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]


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


@dataclass
class Key:
    label: str
    kind: str = "char"   # char, bs, enter, shift, space, sym, lang, left, right, close, spacer
    weight: float = 1.0


def _chars(s):
    return [Key(c) for c in s]


def _layout(name):
    spacer = lambda w: Key("", "spacer", w)
    bottom = [Key("ABC" if name == "sym" else "&123", "sym", 1.5), Key("עב" if name == "en" else "EN", "lang", 1.5),
              Key("", "space", 5), Key("◀", "left"), Key("▶", "right"), Key("✕", "close", 1.5)]
    digits = _chars("1234567890") + [Key("⌫", "bs", 1.5)]
    if name == "en":
        return [digits,
                [spacer(.75)] + _chars("qwertyuiop") + [spacer(.75)],
                _chars("asdfghjkl'") + [Key("⏎", "enter", 1.5)],
                [Key("⇧", "shift", 1.5)] + _chars("zxcvbnm,.?"), bottom]
    if name == "he":
        return [digits,
                _chars("/'קראטוןםפ") + [spacer(1.5)],
                _chars("שדגכעיחלךף") + [Key("⏎", "enter", 1.5)],
                [spacer(1.5)] + _chars("זסבהנמצתץ."), bottom]
    return [digits,
            [spacer(.75)] + _chars("!@#$%^&*()") + [spacer(.75)],
            _chars("-_=+[]{}\\|") + [Key("⏎", "enter", 1.5)],
            [spacer(1.5)] + _chars("~`;:\"<>/?."), bottom]


BG, KEY, KEY_SPECIAL = "#1c1c1c", "#383838", "#2a2a2a"
GREEN, CYAN, TEXT, DIM = "#107c10", "#7dddf0", "#f0f0f0", "#999999"


class Keyboard:
    def __init__(self, screen_w, screen_h):
        self.sw, self.sh = screen_w, screen_h
        self.visible = False
        self.root = self.canvas = None
        self.layout, self.last_letters = "en", "en"
        self.shift = False
        self.row, self.col = 1, 5
        self.rows = _layout("en")

    # ---- window --------------------------------------------------------
    def _build(self):
        self.key_h = int(self.sh * 0.062)
        self.gap = max(3, int(self.key_h * 0.12))
        self.hint_h = int(self.key_h * 0.6)
        self.w = int(self.sw * 0.62)
        self.h = self.gap * 2 + 5 * self.key_h + 4 * self.gap + self.hint_h
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=BG)
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.root.geometry(f"{self.w}x{self.h}+{(self.sw - self.w) // 2}+{self.sh - self.h - int(self.sh * 0.04)}")

    def _no_activate(self):
        self.root.update_idletasks()
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2)  # GA_ROOT
        ex = user32.GetWindowLongW(hwnd, -20)
        # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST: never steals focus from the app being typed into.
        user32.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x00000080 | 0x00000008)

    def show(self):
        if self.root is None:
            self._build()
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self._no_activate()
        self.visible = True
        self.draw()
        self.root.update()

    def hide(self):
        if self.root is not None:
            self.root.withdraw()
        self.visible = False

    def toggle(self):
        self.hide() if self.visible else self.show()

    def destroy(self):
        if self.root is not None:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None

    def pump(self):
        if self.visible and self.root is not None:
            try:
                self.root.update()
            except tk.TclError:
                self.visible = False

    # ---- layout --------------------------------------------------------
    def rects(self):
        out = []
        for r, row in enumerate(self.rows):
            total = sum(k.weight for k in row)
            unit = (self.w - 2 * self.gap) / total
            y0 = self.gap + r * (self.key_h + self.gap)
            x = self.gap
            line = []
            for k in row:
                x1 = x + unit * k.weight
                line.append((x, y0, x1 - self.gap, y0 + self.key_h))
                x = x1
            out.append(line)
        return out

    def _step_h(self, d):
        row = self.rows[self.row]
        c = self.col
        while 0 <= c + d < len(row):
            c += d
            if row[c].kind != "spacer":
                self.col = c
                return

    def _step_v(self, d):
        r = self.row + d
        if not 0 <= r < len(self.rows):
            return
        rects = self.rects()
        cur = rects[self.row][self.col]
        cx = (cur[0] + cur[2]) / 2
        best = min((abs((x0 + x1) / 2 - cx), i) for i, (x0, _, x1, _) in enumerate(rects[r])
                   if self.rows[r][i].kind != "spacer")
        self.row, self.col = r, best[1]

    def _set_layout(self, name):
        rects = self.rects()
        cur = rects[self.row][self.col]
        cx = (cur[0] + cur[2]) / 2
        self.layout = name
        if name != "sym":
            self.last_letters = name
        self.rows = _layout(name)
        new = self.rects()[self.row]
        self.col = min((abs((x0 + x1) / 2 - cx), i) for i, (x0, _, x1, _) in enumerate(new)
                       if self.rows[self.row][i].kind != "spacer")[1]

    # ---- input ---------------------------------------------------------
    def handle(self, ev):
        if ev in ("guide", "y"):
            return self.hide()
        if ev == "left": self._step_h(-1)
        elif ev == "right": self._step_h(1)
        elif ev == "up": self._step_v(-1)
        elif ev == "down": self._step_v(1)
        elif ev == "a": self.press(self.rows[self.row][self.col])
        elif ev == "b": send_vk(0x08)
        elif ev == "x": send_text(" ")
        elif ev == "start": send_vk(0x0D)
        elif ev == "lb": send_vk(0x25)
        elif ev == "rb": send_vk(0x27)
        if self.visible:
            self.draw()

    def press(self, key):
        k = key.kind
        if k == "char":
            send_text(key.label.upper() if self.shift else key.label)
            self.shift = False
        elif k == "bs": send_vk(0x08)
        elif k == "enter": send_vk(0x0D)
        elif k == "space": send_text(" ")
        elif k == "left": send_vk(0x25)
        elif k == "right": send_vk(0x27)
        elif k == "shift": self.shift = not self.shift
        elif k == "sym": self._set_layout(self.last_letters if self.layout == "sym" else "sym")
        elif k == "lang": self._set_layout("he" if self.layout == "en" else "en")
        elif k == "close": self.hide()

    # ---- drawing -------------------------------------------------------
    def _round(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def draw(self):
        c = self.canvas
        c.delete("all")
        size = -int(self.key_h * 0.42)
        font = ("Segoe UI", size)
        sym_font = ("Segoe UI Symbol", size)
        rad = int(self.key_h * 0.16)
        for r, line in enumerate(self.rects()):
            for i, (x0, y0, x1, y1) in enumerate(line):
                key = self.rows[r][i]
                if key.kind == "spacer":
                    continue
                selected = (r, i) == (self.row, self.col)
                active = key.kind == "shift" and self.shift
                fill = GREEN if selected else ("#3d6b3d" if active else (KEY if key.kind == "char" else KEY_SPECIAL))
                self._round(x0, y0, x1, y1, rad, fill=fill, outline=CYAN if selected else "", width=3)
                label = key.label.upper() if key.kind == "char" and self.shift else key.label
                special = key.kind in ("bs", "enter", "shift", "left", "right", "close")
                c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, fill=TEXT,
                              font=sym_font if special else font)
        c.create_text(self.w / 2, self.h - self.hint_h / 2 - 2, fill=DIM, font=("Segoe UI", -int(self.hint_h * 0.5)),
                      text="A Type    B Delete    X Space    Start Enter    LB/RB Cursor    Y Close")
