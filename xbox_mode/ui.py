"""Full-screen console shell: the Guide task switcher (carousel of running apps) and the Xbox home app."""
import atexit
import ctypes
import os
import time
from dataclasses import dataclass

os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")

import pygame

from . import apps as appmod
from . import gdi, winman
from .keyboard import Keyboard
from .mouse import MouseMode
from .xinput import Pad

BG = (16, 16, 16)
PANEL = (32, 32, 32)
GREEN = (16, 124, 16)
GREEN_HI = (107, 199, 107)
CYAN = (125, 221, 240)
TEXT = (240, 240, 240)
DIM = (150, 150, 150)
TABS = ["Home", "Library", "Settings"]
MODES = ["Xbox full screen experience", "Windows desktop"]
KEYMAP = {
    pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
    pygame.K_RETURN: "a", pygame.K_ESCAPE: "b", pygame.K_x: "x", pygame.K_y: "y",
    pygame.K_q: "lb", pygame.K_e: "rb", pygame.K_F1: "guide",
}
REF_W, REF_H = 725, 417  # coordinates below are measured on a 725x417 reference screenshot


@dataclass
class Card:
    title: str
    win: object = None
    preview: object = None
    icon: object = None


def tile_color(name):
    h = sum(ord(c) * (i + 3) for i, c in enumerate(name))
    return (40 + h * 7 % 90, 40 + h * 13 % 90, 60 + h * 29 % 120)


def battery_percent():
    class Status(ctypes.Structure):
        _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte),
                    ("sys", ctypes.c_ubyte), ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
    s = Status()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)) and s.pct <= 100:
        return s.pct
    return 100


def xbox_logo(surf, cx, cy, r):
    pygame.draw.circle(surf, (16, 124, 16), (cx, cy), r)
    pygame.draw.circle(surf, (235, 235, 235), (cx, cy), r, max(1, r // 8))
    d = r * 0.5
    pygame.draw.line(surf, (235, 235, 235), (cx - d, cy - d), (cx + d, cy + d), max(2, r // 4))
    pygame.draw.line(surf, (235, 235, 235), (cx + d, cy - d), (cx - d, cy + d), max(2, r // 4))


class Launcher:
    def __init__(self, size, windowed=False):
        self.w, self.h = size
        self.k = self.h / REF_H
        self.screen = pygame.display.set_mode(size, 0 if windowed else pygame.NOFRAME)
        pygame.display.set_caption("Xbox Mode")
        k = self.k
        font = lambda px, bold=False: pygame.font.SysFont("segoeuisemibold" if bold else "segoeui", max(8, int(px * k)))
        self.f_card, self.f_hint, self.f_time = font(17), font(12), font(17, True)
        self.f_mode, self.f_lb = font(9.5), font(7, True)
        self.f_big, self.f_mid, self.f_small = font(40, True), font(22), font(16)
        self.bg = self.make_background()
        self.cfg = appmod.load_config()
        self.apps = appmod.scan()
        self.view = "switcher"
        self.zone = "cards"
        self.mode_sel = 0
        self.cards, self.card_sel, self.scroll = [], 0, 0.0
        self.prev_fg = 0
        self.tab, self.sel = 0, {0: 0, 1: 0, 2: 0}
        self.mouse = MouseMode()
        self.running = True
        self.hwnd = pygame.display.get_wm_info().get("window", 0)
        self.apply_taskbar()
        atexit.register(winman.set_taskbar_visible, True)

    # ---- helpers -------------------------------------------------------
    def X(self, x): return int(x * self.w / REF_W)
    def Y(self, y): return int(y * self.h / REF_H)

    def make_background(self):
        sw, sh = 96, 54
        small = pygame.Surface((sw, sh))
        for y in range(sh):
            for x in range(sw):
                d = (((x - sw / 2) / (sw * 0.62)) ** 2 + ((y - sh * 0.38) / (sh * 0.75)) ** 2) ** 0.5
                v = int(max(14, 58 - 48 * min(1.0, d)))
                small.set_at((x, y), (v, v, v))
        return pygame.transform.smoothscale(small, (self.w, self.h))

    def text(self, s, font, color, pos, center=False, right=False):
        surf = font.render(s, True, color)
        r = surf.get_rect()
        if center: r.center = pos
        elif right: r.topright = pos
        else: r.topleft = pos
        self.screen.blit(surf, r)
        return r

    def fit(self, s, font, width):
        if font.size(s)[0] <= width:
            return s
        while s and font.size(s + "…")[0] > width:
            s = s[:-1]
        return s + "…"

    # ---- settings ------------------------------------------------------
    def apply_taskbar(self):
        winman.set_taskbar_visible(not self.cfg["hide_taskbar"])

    def toggle(self, key):
        self.cfg[key] = not self.cfg[key]
        appmod.save_config(self.cfg)
        if key == "hide_taskbar":
            self.apply_taskbar()

    def settings_items(self):
        return [
            (f"Hide taskbar: {'On' if self.cfg['hide_taskbar'] else 'Off'}", lambda: self.toggle("hide_taskbar")),
            (f"Controller as mouse on desktop: {'On' if self.cfg['mouse_mode'] else 'Off'}",
             lambda: self.toggle("mouse_mode")),
            ("Rescan installed apps", self.rescan),
            ("Exit Xbox Mode", self.quit),
        ]

    def rescan(self):
        self.apps = appmod.scan()

    def quit(self):
        winman.set_taskbar_visible(True)
        self.running = False

    # ---- switcher state ------------------------------------------------
    def open_switcher(self):
        fg = winman.foreground()
        self.prev_fg = fg if fg != self.hwnd else self.prev_fg
        xbox = Card("Xbox", icon=None)
        xbox.preview = self.render_home_preview()
        cards = [xbox]
        for w in winman.list_windows(exclude=(self.hwnd,)):
            cards.append(Card(w.title, w, gdi.capture_window(w.hwnd), gdi.window_icon(w.hwnd, w.path)))
        self.cards = cards
        self.card_sel = next((i for i, c in enumerate(cards) if c.win and c.win.hwnd == self.prev_fg), 0)
        self.scroll = float(self.card_sel)
        self.zone, self.mode_sel, self.view = "cards", 0, "switcher"
        winman.focus(self.hwnd)

    def close_switcher(self):
        if self.prev_fg and self.prev_fg != self.hwnd:
            winman.focus(self.prev_fg)

    def render_home_preview(self):
        off = pygame.Surface((self.w, self.h))
        real, self.screen = self.screen, off
        try:
            self.draw_home(footer=False)
        finally:
            self.screen = real
        return off

    # ---- input ---------------------------------------------------------
    def handle(self, ev):
        if self.view == "switcher":
            self.handle_switcher(ev)
        else:
            self.handle_home(ev)

    def handle_switcher(self, ev):
        n = len(self.cards)
        if ev == "guide" or (ev == "b" and self.zone == "cards"):
            self.close_switcher()
        elif self.zone == "modes":
            if ev == "left": self.mode_sel = max(0, self.mode_sel - 1)
            elif ev == "right": self.mode_sel = min(len(MODES) - 1, self.mode_sel + 1)
            elif ev in ("up", "b"): self.zone = "cards"
            elif ev == "a":
                if self.mode_sel == 1:
                    self.quit()
                else:
                    self.zone = "cards"
        else:
            if ev in ("left", "lb"): self.card_sel = max(0, self.card_sel - 1)
            elif ev in ("right", "rb"): self.card_sel = min(n - 1, self.card_sel + 1)
            elif ev == "down": self.zone = "modes"
            elif ev == "a":
                card = self.cards[self.card_sel]
                if card.win:
                    winman.focus(card.win.hwnd)
                else:
                    self.view = "home"
            elif ev == "x" and self.cards[self.card_sel].win:
                winman.close(self.cards[self.card_sel].win.hwnd)
                del self.cards[self.card_sel]
                self.card_sel = min(self.card_sel, len(self.cards) - 1)

    def home_items(self):
        return appmod.recent(self.apps, self.cfg)

    def list_for_tab(self):
        return self.home_items() if self.tab == 0 else self.apps if self.tab == 1 else []

    def handle_home(self, ev):
        if ev in ("guide", "b"):
            return self.open_switcher()
        if ev == "lb":
            self.tab = (self.tab - 1) % len(TABS)
        elif ev == "rb":
            self.tab = (self.tab + 1) % len(TABS)
        elif self.tab == 2:
            items = self.settings_items()
            s = self.sel[2]
            if ev == "up": self.sel[2] = max(0, s - 1)
            elif ev == "down": self.sel[2] = min(len(items) - 1, s + 1)
            elif ev == "a": items[s][1]()
        else:
            items = self.list_for_tab()
            cols = 5 if self.tab == 1 else max(1, len(items))
            s = self.sel[self.tab]
            if ev == "left": s -= 1
            elif ev == "right": s += 1
            elif ev == "up" and self.tab == 1: s -= cols
            elif ev == "down" and self.tab == 1: s += cols
            elif ev == "a" and items:
                appmod.launch(items[min(s, len(items) - 1)], self.cfg)
            elif ev == "y":
                self.rescan()
            self.sel[self.tab] = max(0, min(len(items) - 1, s)) if items else 0

    # ---- drawing: switcher ---------------------------------------------
    def draw(self):
        if self.view == "switcher":
            self.draw_switcher()
        else:
            self.draw_home()
        pygame.display.flip()

    def draw_switcher(self):
        self.screen.blit(self.bg, (0, 0))
        self.draw_top_bar()
        self.scroll += (self.card_sel - self.scroll) * 0.22
        cw, ch = self.X(343), self.Y(237)
        pitch = self.X(365)
        base_x, y = self.X(190), self.Y(92)
        order = sorted(range(len(self.cards)), key=lambda i: -abs(i - self.card_sel))
        for i in order:
            x = base_x + int((i - self.scroll) * pitch)
            if x > self.w or x + cw < 0:
                continue
            self.draw_card(self.cards[i], pygame.Rect(x, y, cw, ch), i == self.card_sel and self.zone == "cards")
        self.draw_bottom_bar()

    def draw_card(self, card, rect, selected):
        hdr = self.Y(40)
        pygame.draw.rect(self.screen, (26, 26, 26), rect, border_radius=self.X(5))
        body = pygame.Rect(rect.x, rect.y + hdr, rect.w, rect.h - hdr)
        if card.preview:
            pw, ph = card.preview.get_size()
            scale = max(body.w / pw, body.h / ph)
            scaled = pygame.transform.smoothscale(card.preview, (max(1, int(pw * scale)), max(1, int(ph * scale))))
            self.screen.set_clip(body)
            self.screen.blit(scaled, scaled.get_rect(midtop=(body.centerx, body.y)))
            self.screen.set_clip(None)
        else:
            pygame.draw.rect(self.screen, tile_color(card.title), body)
        ic = self.Y(22)
        icon_pos = (rect.x + self.X(11), rect.y + (hdr - ic) // 2)
        if card.win is None:
            xbox_logo(self.screen, icon_pos[0] + ic // 2, icon_pos[1] + ic // 2, ic // 2)
        elif card.icon:
            self.screen.blit(pygame.transform.smoothscale(card.icon, (ic, ic)), icon_pos)
        title_x = rect.x + self.X(38)
        self.text(self.fit(card.title, self.f_card, rect.right - title_x - self.X(12)), self.f_card, TEXT,
                  (title_x, rect.y + (hdr - self.f_card.get_height()) // 2))
        if selected:
            pygame.draw.rect(self.screen, CYAN, rect.inflate(6, 6), max(2, self.Y(2)), border_radius=self.X(7))
            hx, hy = rect.x + self.X(13), rect.bottom - self.Y(25)
            hx = self.hint(hx, hy, "A", "Select")
            if card.win:
                self.hint(hx + self.X(14), hy, "X", "Close App")

    def hint(self, x, y, glyph, label):
        r = self.Y(7)
        pygame.draw.circle(self.screen, TEXT, (x + r, y + r + 1), r, max(1, self.Y(1)))
        self.text(glyph, self.f_lb, TEXT, (x + r, y + r + 1), center=True)
        return self.text(label, self.f_hint, TEXT, (x + 2 * r + self.X(5), y + r + 1 - self.f_hint.get_height() // 2)).right

    def draw_top_bar(self):
        cy = self.Y(28)
        n = len(self.cards)
        first = max(0, min(self.card_sel - 4, n - 9))
        visible = list(range(first, min(n, first + 9)))
        spacing = self.X(36)
        cx = self.X(362)
        half = len(visible) * spacing // 2
        self.pill("LB", (cx - half - self.X(14), cy))
        self.pill("RB", (cx + half + self.X(15), cy))
        for slot, i in enumerate(visible):
            ix = cx - half + spacing // 2 + slot * spacing
            card = self.cards[i]
            sel = i == self.card_sel
            size = self.Y(33 if sel else 20)
            if sel:
                box = pygame.Rect(0, 0, size, size)
                box.center = (ix, cy)
                pygame.draw.rect(self.screen, (60, 60, 60), box, border_radius=self.X(5))
            if card.win is None:
                xbox_logo(self.screen, ix, cy, int(size * (0.34 if sel else 0.5)))
            elif card.icon:
                s = int(size * 0.72) if sel else size
                self.screen.blit(pygame.transform.smoothscale(card.icon, (s, s)), (ix - s // 2, cy - s // 2))
            else:
                pygame.draw.circle(self.screen, tile_color(card.title), (ix, cy), size // 3)
        self.draw_status(cy)

    def pill(self, label, center):
        w, h = self.X(16), self.Y(12)
        r = pygame.Rect(0, 0, w, h)
        r.center = center
        pygame.draw.rect(self.screen, (50, 50, 50), r, border_radius=self.X(4))
        pygame.draw.rect(self.screen, (170, 170, 170), r, 1, border_radius=self.X(4))
        self.text(label, self.f_lb, TEXT, r.center, center=True)

    def draw_status(self, cy):
        t = time.strftime("%I:%M %p").lstrip("0")
        tr = self.text(t, self.f_time, TEXT, (self.X(719), cy - self.f_time.get_height() // 2), right=True)
        # battery
        bw, bh = self.X(15), self.Y(8)
        bx = tr.left - self.X(14) - bw
        body = pygame.Rect(bx, cy - bh // 2, bw, bh)
        pygame.draw.rect(self.screen, TEXT, body, 1, border_radius=2)
        pygame.draw.rect(self.screen, TEXT, (body.right + 1, cy - bh // 5, 2, bh // 2 + 1))
        fill = body.inflate(-4, -4)
        fill.w = max(1, int(fill.w * battery_percent() / 100))
        pygame.draw.rect(self.screen, TEXT, fill)
        # speaker
        sx = bx - self.X(22)
        sp = self.Y(4)
        pygame.draw.polygon(self.screen, TEXT, [(sx, cy - sp // 2), (sx + sp, cy - sp // 2), (sx + 2 * sp, cy - sp),
                                                (sx + 2 * sp, cy + sp), (sx + sp, cy + sp // 2), (sx, cy + sp // 2)])
        for rad in (sp, 2 * sp):
            pygame.draw.arc(self.screen, TEXT, (sx + sp * 2 - rad // 2, cy - rad, rad * 2, rad * 2), -0.9, 0.9, 1)
        # wifi
        wx = sx - self.X(22)
        for rad in (self.Y(3), self.Y(6), self.Y(9)):
            pygame.draw.arc(self.screen, TEXT, (wx - rad, cy + self.Y(5) - rad, rad * 2, rad * 2), 0.8, 2.34, 2)
        pygame.draw.circle(self.screen, TEXT, (wx, cy + self.Y(5)), max(1, self.Y(1)))

    def draw_bottom_bar(self):
        top = self.Y(383)
        pygame.draw.rect(self.screen, (22, 22, 22), (0, top, self.w, self.h - top))
        pygame.draw.line(self.screen, (58, 58, 58), (0, top), (self.w, top))
        ih, gap, pad = self.Y(24), self.X(7), self.X(8)
        widths = [self.f_mode.size(m)[0] + self.X(18) + pad * 2 for m in MODES]
        x = self.w // 2 - (sum(widths) + gap) // 2
        for i, (label, width) in enumerate(zip(MODES, widths)):
            box = pygame.Rect(x, top + self.Y(3), width, ih)
            if i == 0:
                pygame.draw.rect(self.screen, (58, 58, 58), box, border_radius=self.X(3))
                pygame.draw.rect(self.screen, TEXT, (box.centerx - self.X(5), box.bottom - self.Y(3), self.X(10), self.Y(2)))
                xbox_logo(self.screen, box.x + pad + self.X(6), box.centery, self.X(5))
            else:
                self.windows_logo(box.x + pad, box.centery, self.X(11))
            if self.zone == "modes" and i == self.mode_sel:
                pygame.draw.rect(self.screen, CYAN, box.inflate(4, 4), max(2, self.Y(1.5)), border_radius=self.X(5))
            self.text(label, self.f_mode, TEXT if i == 0 else DIM,
                      (box.x + pad + self.X(18), box.centery - self.f_mode.get_height() // 2))
            x += width + gap

    def windows_logo(self, x, cy, size):
        q = size // 2 - 1
        for dx in (0, q + 1):
            for dy in (0, q + 1):
                pygame.draw.rect(self.screen, (180, 180, 180), (x + dx, cy - size // 2 + dy, q, q))

    # ---- drawing: home app ---------------------------------------------
    def draw_tile(self, app, rect, selected):
        pygame.draw.rect(self.screen, tile_color(app.name), rect, border_radius=14)
        self.text(app.name[:1].upper(), self.f_big, TEXT, rect.center, center=True)
        self.text(self.fit(app.name, self.f_small, rect.w), self.f_small, TEXT, (rect.x, rect.bottom + 10))
        if selected:
            pygame.draw.rect(self.screen, GREEN_HI, rect.inflate(12, 12), 5, border_radius=18)

    def draw_home(self, footer=True):
        self.screen.fill(BG)
        pad = self.X(40)
        x = pad
        for i, name in enumerate(TABS):
            self.text(name, self.f_mid, TEXT if i == self.tab else DIM, (x, self.Y(20)))
            if i == self.tab:
                pygame.draw.rect(self.screen, GREEN_HI, (x, self.Y(52), self.X(40), 4))
            x += self.X(95)
        tw, th = self.X(120), self.Y(120)
        if self.tab == 2:
            for i, (label, _) in enumerate(self.settings_items()):
                r = pygame.Rect(pad, self.Y(90) + i * self.Y(46), self.w - 2 * pad, self.Y(38))
                pygame.draw.rect(self.screen, GREEN if i == self.sel[2] else PANEL, r, border_radius=10)
                self.text(label, self.f_mid, TEXT, (r.x + 16, r.y + (r.h - self.f_mid.get_height()) // 2))
        else:
            items = self.list_for_tab()
            if not items:
                self.text("No apps found. Press Y to rescan.", self.f_mid, DIM, (pad, self.Y(100)))
            elif self.tab == 0:
                for i, a in enumerate(items):
                    self.draw_tile(a, pygame.Rect(pad + i * (tw + self.X(16)), self.Y(120), tw, th), i == self.sel[0])
            else:
                sel = self.sel[1]
                cols = 5
                row_off = max(0, sel // cols - 1)
                for i, a in enumerate(items):
                    row, col = divmod(i, cols)
                    row -= row_off
                    if 0 <= row < 3:
                        self.draw_tile(a, pygame.Rect(pad + col * (tw + self.X(16)), self.Y(85) + row * self.Y(100),
                                                      tw, self.Y(80)), i == sel)
        if footer:
            hint = "A Launch   Y Rescan   LB/RB Tabs   B / Guide Switcher" if self.tab < 2 else "A Select   LB/RB Tabs"
            self.text(hint, self.f_small, DIM, (pad, self.h - self.Y(28)))


def run(smoke_frames=0, windowed=False):
    ctypes.windll.user32.SetProcessDPIAware()
    pygame.init()
    size = (1280, 720) if windowed else winman.screen_size()
    ui = Launcher(size, windowed)
    ui.open_switcher()
    pad = Pad()
    keyboard = Keyboard(*size)
    clock = pygame.time.Clock()
    last = time.monotonic()
    frames = 0
    while ui.running:
        now = time.monotonic()
        dt, last = now - last, now
        events = []
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                ui.quit()
            elif e.type == pygame.KEYDOWN and e.key in KEYMAP:
                events.append(KEYMAP[e.key])
        fg = winman.foreground()
        in_ui = fg == ui.hwnd or not ui.hwnd
        pad.stick_nav = in_ui or keyboard.visible
        pad.update(now)
        events += pad.events()

        if in_ui:
            keyboard.hide()
            for ev in events:
                ui.handle(ev)
            ui.draw()
        elif "guide" in pad.pressed or "guide" in events:
            keyboard.hide()
            ui.open_switcher()
        elif keyboard.visible:
            for ev in pad.events():
                keyboard.handle(ev)
        elif ui.cfg["mouse_mode"] and not winman.is_fullscreen(fg):
            if "y" in pad.pressed:
                keyboard.show()
            else:
                ui.mouse.apply(pad, dt)
        keyboard.pump()
        clock.tick(60)
        frames += 1
        if smoke_frames and frames == smoke_frames - 1:
            pygame.image.save(ui.screen, "smoke.png")
        if smoke_frames and frames >= smoke_frames:
            ui.quit()
    keyboard.destroy()
    pygame.quit()
