"""System layer for Xbox Mode. No UI: it owns the gamepad, windows, apps and input injection,
and talks to the Electron UI with newline-delimited JSON over stdin/stdout.

UI -> engine: {"id": n, "cmd": "...", ...args}   engine -> UI: {"t": "res", "id": n, "data": ...}
Engine events: {"t": "btn", "name", "target": "ui"|"kb"}, {"t": "guide"}, {"t": "toggle_kb"}, {"t": "pad", "connected"}

Outside the Xbox UI the left stick drives the mouse, except in "game" windows, which keep the controller to
themselves: exclusive full-screen Direct3D apps, plus any app you flag with Back+Start (a beep confirms).
"""
import ctypes
import json
import queue
import sys
import threading
import time
import winsound

from . import apps as appmod
from . import winman
from .mouse import MouseMode
from .sendinput import send_text, send_vk
from .xinput import Pad

TICK = 1 / 125
WATCH_SECONDS = 45
WINDOWLESS_AFTER = 2  # launches in a row that showed no window before an app is hidden
D3D_EXCLUSIVE = 3  # QUNS_RUNNING_D3D_FULL_SCREEN
shell32 = ctypes.windll.shell32


class Engine:
    def __init__(self):
        self.pad = Pad()
        self.mouse = MouseMode()
        self.cfg = appmod.load_config()
        self.ui_hwnd = 0
        self.kb_visible = False
        self.taskbar_hidden = False
        self.inbox = queue.Queue()
        self.running = True
        self.was_connected = None
        self.launch = None  # the launch being observed: deadline, windows that existed, whether one showed up
        self.next_watch = 0.0
        self.exclusive = False
        self.next_exclusive_check = 0.0

    # ---- io ------------------------------------------------------------
    def emit(self, obj):
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def read_stdin(self):
        for line in sys.stdin:
            line = line.strip()
            if line:
                try:
                    self.inbox.put(json.loads(line))
                except ValueError:
                    pass
        self.inbox.put({"cmd": "quit"})

    # ---- commands ------------------------------------------------------
    def set_taskbar(self, visible):
        winman.set_taskbar_visible(visible)
        self.taskbar_hidden = not visible

    def handle(self, msg):
        cmd = msg.get("cmd")
        data = None
        if cmd == "ui":
            self.ui_hwnd = msg["hwnd"]
        elif cmd == "kb":
            self.kb_visible = bool(msg["visible"])
        elif cmd == "apply_taskbar":
            self.set_taskbar(not self.cfg["hide_taskbar"])
        elif cmd == "taskbar":
            self.set_taskbar(bool(msg["visible"]))
        elif cmd == "windows":
            data = [w.__dict__ for w in winman.list_windows(exclude=(self.ui_hwnd,))]
        elif cmd == "apps":
            usage = self.cfg["usage"]
            hidden = set(self.cfg["hidden_apps"]) | {p for p, n in self.cfg["windowless"].items()
                                                     if n >= WINDOWLESS_AFTER}
            data = [{"name": a.name, "path": a.path, "folder": a.folder, "last": usage.get(a.path, 0)}
                    for a in appmod.scan() if a.path not in hidden]
        elif cmd == "launch":
            appmod.launch(appmod.App(msg.get("name", ""), msg["path"]), self.cfg)
            seen = {w.hwnd for w in winman.list_windows(exclude=(self.ui_hwnd,))}
            self.launch = {"path": msg["path"], "deadline": time.monotonic() + WATCH_SECONDS, "seen": seen,
                           "shown": False}
        elif cmd == "foreground":
            data = winman.foreground()
        elif cmd == "focus":
            winman.focus(msg["hwnd"])
        elif cmd == "close":
            winman.close(msg["hwnd"])
        elif cmd == "config_get":
            data = {k: v for k, v in self.cfg.items() if k != "usage"}
        elif cmd == "config_set":
            self.cfg[msg["key"]] = msg["value"]
            appmod.save_config(self.cfg)
            if msg["key"] == "hide_taskbar":
                self.set_taskbar(not msg["value"])
        elif cmd == "type":
            send_text(msg["text"])
        elif cmd == "vk":
            send_vk(msg["code"])
        elif cmd == "quit":
            self.running = False
        if "id" in msg:
            self.emit({"t": "res", "id": msg["id"], "data": data})

    # ---- policy --------------------------------------------------------
    def is_game(self, fg, now):
        if winman.exe_name(fg).lower() in {a.lower() for a in self.cfg["game_apps"]}:
            return True
        # The shell reports an exclusive full-screen app even while a small pop-up sits in front of it, so the
        # pop-up must not inherit "game" status: only the window that actually covers the screen counts.
        if not winman.covers_screen(fg):
            return False
        if now >= self.next_exclusive_check:
            state = ctypes.c_int(0)
            if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
                self.exclusive = state.value == D3D_EXCLUSIVE
            self.next_exclusive_check = now + 0.5
        return self.exclusive

    def toggle_game(self, fg):
        exe = winman.exe_name(fg)
        if not exe:
            return
        games = self.cfg["game_apps"]
        match = next((g for g in games if g.lower() == exe.lower()), None)
        if match:
            games.remove(match)
        else:
            games.append(exe)
        appmod.save_config(self.cfg)
        threading.Thread(target=winsound.Beep, args=(440 if match else 880, 140), daemon=True).start()

    def watch_launch(self, now):
        """Watches a freshly launched app: makes its new windows full screen and learns whether it shows any window."""
        watch = self.launch
        fg = winman.foreground()
        if fg and fg != self.ui_hwnd:
            watch["shown"] = True  # something other than our UI came to the front, e.g. an app that was already running
        for w in winman.list_windows(exclude=(self.ui_hwnd,)):
            if w.hwnd not in watch["seen"]:
                watch["seen"].add(w.hwnd)
                watch["shown"] = True
                if self.cfg["launch_fullscreen"]:
                    winman.fullscreenize(w.hwnd)
        if now > watch["deadline"]:
            self.launch = None
            self.record_launch(watch["path"], watch["shown"])

    def record_launch(self, path, shown):
        known, misses = self.cfg["has_window"], self.cfg["windowless"]
        if shown:
            if path not in known:
                known.append(path)
            misses.pop(path, None)
        elif path not in known:  # an app that has shown a window before is never hidden for a slow start
            misses[path] = misses.get(path, 0) + 1
        appmod.save_config(self.cfg)

    # ---- gamepad -------------------------------------------------------
    def tick(self, now, dt):
        fg = winman.foreground()
        in_ui = bool(self.ui_hwnd) and fg == self.ui_hwnd
        self.pad.stick_nav = in_ui or self.kb_visible
        self.pad.update(now)
        pad = self.pad
        if pad.connected != self.was_connected:
            self.was_connected = pad.connected
            self.emit({"t": "pad", "connected": pad.connected})
        if self.launch and now >= self.next_watch:
            self.next_watch = now + 0.5
            self.watch_launch(now)

        chord = ("back" in pad.pressed and "start" in pad.held) or ("start" in pad.pressed and "back" in pad.held)
        if "guide" in pad.pressed:
            self.emit({"t": "guide"})
        elif in_ui or self.kb_visible:
            target = "kb" if self.kb_visible else "ui"
            for name in pad.events():
                if name != "guide":
                    self.emit({"t": "btn", "name": name, "target": target})
        elif chord:
            self.toggle_game(fg)
        elif self.cfg["mouse_mode"] and not self.is_game(fg, now):
            if "y" in pad.pressed:
                self.emit({"t": "toggle_kb"})
            else:
                self.mouse.apply(pad, dt)

    def run(self):
        threading.Thread(target=self.read_stdin, daemon=True).start()
        last = time.monotonic()
        try:
            while self.running:
                now = time.monotonic()
                dt, last = now - last, now
                while True:
                    try:
                        self.handle(self.inbox.get_nowait())
                    except queue.Empty:
                        break
                self.tick(now, dt)
                time.sleep(TICK)
        finally:
            if self.taskbar_hidden:
                winman.set_taskbar_visible(True)


def setup_io():
    # Piped stdio defaults to the ANSI code page on Windows, which mangles Hebrew; the UI speaks UTF-8.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    setup_io()
    ctypes.windll.user32.SetProcessDPIAware()  # so window coordinates are physical pixels
    Engine().run()
