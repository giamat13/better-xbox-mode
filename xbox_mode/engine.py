"""System layer for Xbox Mode. No UI: it owns the gamepad, windows, apps and input injection,
and talks to the Electron UI with newline-delimited JSON over stdin/stdout.

UI -> engine: {"id": n, "cmd": "...", ...args}   engine -> UI: {"t": "res", "id": n, "data": ...}
Engine events: {"t": "btn", "name", "target": "ui"|"kb"}, {"t": "guide"}, {"t": "toggle_kb"}, {"t": "pad", "connected"}

Outside the Xbox UI the left stick drives the mouse, except in "game" windows, which keep the controller to
themselves: only the Guide button stays ours. A game is a window whose process reads the controller (it has loaded
XInput, DirectInput, SDL, GameInput or Steam's API), runs exclusive Direct3D full screen, or cannot be inspected
(protected). The switcher shows what was detected and flips it per app with Y; the choice is remembered.
"""
import ctypes
import json
import queue
import sys
import threading
import time

from . import apps as appmod
from . import winman
from .mouse import MouseMode
from .sendinput import send_text, send_vk
from .xinput import Pad

TICK = 1 / 125
WATCH_SECONDS = 45
STEAM_GUARD_SECONDS = 4  # after Guide, how long a Steam window that takes the screen is pushed back
STEAM_EXES = {"steam.exe", "steamwebhelper.exe"}
STEAM_MAX_PUSHES = 3
WINDOWLESS_AFTER = 2  # launches in a row that showed no window before an app is hidden
D3D_EXCLUSIVE = 3  # QUNS_RUNNING_D3D_FULL_SCREEN
AWARE_RECHECK_SECONDS = 2.0
GAMEPAD_DLLS = {"xinput1_1.dll", "xinput1_2.dll", "xinput1_3.dll", "xinput1_4.dll", "xinput9_1_0.dll", "dinput.dll",
                "dinput8.dll", "sdl2.dll", "sdl3.dll", "gameinput.dll", "windows.gaming.input.dll", "xinputuap.dll",
                "steam_api.dll", "steam_api64.dll"}
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
        self.aware = {}  # pid -> (checked at, whether the process reads the controller)
        self.guard_until = 0.0
        self.next_guard = 0.0
        self.pushed = 0

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
            now = time.monotonic()
            data = [{**w.__dict__, "game": self.is_game(w.hwnd, now)}
                    for w in winman.list_windows(exclude=(self.ui_hwnd,))]
        elif cmd == "toggle_game":
            data = self.toggle_game(msg["hwnd"], time.monotonic())
        elif cmd == "apps":
            usage = self.cfg["usage"]
            hidden = set(self.cfg["hidden_apps"]) | {p for p, n in self.cfg["windowless"].items()
                                                     if n >= WINDOWLESS_AFTER}
            data = [{"name": a.name, "path": a.path, "folder": a.folder, "last": usage.get(a.path, 0)}
                    for a in appmod.scan() if a.path not in hidden]
        elif cmd == "launch":
            appmod.launch(appmod.App(msg.get("name", ""), msg["path"]), self.cfg)
            seen = {w.hwnd for w in winman.list_windows(exclude=(self.ui_hwnd,))}
            self.launch = {"path": msg["path"], "exe": msg.get("exe", ""), "deadline": time.monotonic() + WATCH_SECONDS,
                           "seen": seen, "shown": False}
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
    def is_game(self, hwnd, now):
        """True when the window's program talks to the controller itself, so the engine must stay out of the way."""
        exe = winman.exe_name(hwnd).lower()
        if exe in {a.lower() for a in self.cfg["mouse_apps"]}:
            return False
        if exe in {a.lower() for a in self.cfg["game_apps"]}:
            return True
        return self.reads_controller(hwnd, now)

    def reads_controller(self, hwnd, now):
        pid = winman.pid_of(hwnd)
        cached = self.aware.get(pid)
        if cached and now - cached[0] < AWARE_RECHECK_SECONDS:
            return cached[1]
        modules = winman.module_names(pid)
        if modules is None:
            # Not inspectable: an anti-cheat protected game or an elevated program. The first must be left alone, and
            # the second ignores injected input anyway, so hands off either way.
            aware = True
        else:
            aware = bool(modules & GAMEPAD_DLLS) or (winman.covers_screen(hwnd) and self.exclusive_fullscreen(now))
        if len(self.aware) > 64:
            self.aware.clear()
        self.aware[pid] = (now, aware)
        return aware

    def exclusive_fullscreen(self, now):
        if now >= self.next_exclusive_check:
            state = ctypes.c_int(0)
            if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
                self.exclusive = state.value == D3D_EXCLUSIVE
            self.next_exclusive_check = now + 0.5
        return self.exclusive

    def toggle_game(self, hwnd, now):
        """Flips a window's program between "game" (keeps the controller) and "mouse"; the choice is remembered."""
        exe = winman.exe_name(hwnd)
        if not exe:
            return False
        make_game = not self.is_game(hwnd, now)
        for key in ("game_apps", "mouse_apps"):
            self.cfg[key] = [a for a in self.cfg[key] if a.lower() != exe.lower()]
        self.cfg["game_apps" if make_game else "mouse_apps"].append(exe)
        self.aware.clear()
        appmod.save_config(self.cfg)
        return make_game

    def reclaim_from_steam(self, fg):
        """Steam listens to the Guide button too and raises its own window over us.

        Push that window back (minimize, never close: closing Big Picture drops Steam into its desktop window) and
        bring the UI forward again, unless the user has just launched an app themselves, which may be Steam."""
        launching_steam = self.launch and self.launch.get("exe", "").lower() in STEAM_EXES
        if (launching_steam or not fg or fg == self.ui_hwnd or winman.exe_name(fg).lower() not in STEAM_EXES
                or self.pushed >= STEAM_MAX_PUSHES):
            return
        self.pushed += 1  # a few tries per Guide press, so a window that keeps coming back cannot start a fight
        winman.minimize(fg)
        winman.focus(self.ui_hwnd)

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
                # Only the launched program's own windows: other programs' windows (Steam popping up, say) stay as is.
                if self.cfg["launch_fullscreen"] and watch["exe"] and w.exe.lower() == watch["exe"].lower():
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

        if now < self.guard_until and now >= self.next_guard:
            self.next_guard = now + 0.1
            self.reclaim_from_steam(fg)

        if "guide" in pad.pressed:
            self.pushed = 0
            self.guard_until = now + STEAM_GUARD_SECONDS
            self.emit({"t": "guide"})
        elif in_ui or self.kb_visible:
            target = "kb" if self.kb_visible else "ui"
            for name in pad.events():
                if name != "guide":
                    self.emit({"t": "btn", "name": name, "target": target})
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
