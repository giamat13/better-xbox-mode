"""Live checks against real Windows APIs. Skipped everywhere except Windows (run by the windows-verify workflow)."""
import ctypes
import os
import subprocess
import sys
import time
import unittest

WINDOWS = sys.platform == "win32"


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _user32():
    return ctypes.WinDLL("user32", use_last_error=True)


def _cursor():
    point = POINT()
    _user32().GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _set_cursor(x, y):
    _user32().SetCursorPos(int(x), int(y))


def _key_down(virtual_key):
    return bool(_user32().GetAsyncKeyState(virtual_key) & 0x8000)


def _engine(backend):
    from xbox_mode.config import load_config
    from xbox_mode.engine import Engine
    from xbox_mode.launcher import Launcher
    from xbox_mode.outputs import KeyboardOutput, MouseOutput
    from xbox_mode.policy import EmulationPolicy

    config = load_config(None)
    return Engine(
        config=config,
        mouse=MouseOutput(backend),
        keyboard=KeyboardOutput(backend),
        launcher=Launcher([]),
        policy=EmulationPolicy({}, 1.0),
        foreground=lambda: (None, "notepad.exe"),
        uses_gamepad=lambda pid, now: False,
        heartbeat=lambda: None,
        toggle_osk=lambda: None,
        launch_app=lambda app: None,
    )


@unittest.skipUnless(WINDOWS, "Windows only")
class WindowsLiveTests(unittest.TestCase):
    def setUp(self):
        from xbox_mode.backend_win import WinInputBackend

        self.backend = WinInputBackend()
        user32 = _user32()
        _set_cursor(user32.GetSystemMetrics(0) // 2, user32.GetSystemMetrics(1) // 2)
        time.sleep(0.1)

    def test_relative_move_moves_the_real_cursor(self):
        before = _cursor()
        self.backend.move_relative(80, 0)
        time.sleep(0.1)
        after = _cursor()
        self.assertGreater(after[0], before[0])
        self.assertLess(abs(after[1] - before[1]), 3)

    def test_left_button_state_is_seen_by_the_system(self):
        self.backend.button("left", True)
        time.sleep(0.05)
        down = _key_down(0x01)
        self.backend.button("left", False)
        time.sleep(0.05)
        self.assertTrue(down)
        self.assertFalse(_key_down(0x01))

    def test_enter_key_state_is_seen_by_the_system(self):
        self.backend.key("enter", True)
        time.sleep(0.05)
        down = _key_down(0x0D)
        self.backend.key("enter", False)
        time.sleep(0.05)
        self.assertTrue(down)

    def test_wheel_is_accepted_by_the_system(self):
        self.backend.wheel(1)
        self.backend.wheel(-1)

    def test_loaded_modules_include_kernel32(self):
        from xbox_mode.system import list_modules

        self.assertIn("kernel32.dll", list_modules(os.getpid()))

    def test_foreground_process_is_reported(self):
        from xbox_mode.system import foreground_process

        pid, _ = foreground_process()
        self.assertIsNotNone(pid)

    def test_process_that_loads_xinput_is_detected_and_plain_process_is_not(self):
        from xbox_mode.gamepad_usage import uses_gamepad_api
        from xbox_mode.system import list_modules

        xinput = subprocess.Popen(
            [sys.executable, "-c", "import ctypes, time; ctypes.WinDLL('xinput1_4.dll'); time.sleep(60)"]
        )
        plain = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            time.sleep(1.5)
            self.assertTrue(uses_gamepad_api(list_modules(xinput.pid)))
            self.assertFalse(uses_gamepad_api(list_modules(plain.pid)))
        finally:
            for child in (xinput, plain):
                child.kill()
                child.wait()

    def test_start_menu_discovery_finds_apps(self):
        from xbox_mode.launcher_apps import discover_apps

        apps = discover_apps([], windows=True)
        print(f"start menu apps discovered: {len(apps)}")
        self.assertGreater(len(apps), 0)

    def test_launching_an_app_starts_a_real_process(self):
        from xbox_mode.launcher_apps import App, launch

        launch(App(name="Notepad", path=os.path.join(os.environ["SystemRoot"], "System32", "notepad.exe")))
        running = False
        for _ in range(40):
            time.sleep(0.2)
            listing = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq notepad.exe", "/NH"], capture_output=True, text=True
            ).stdout
            if "notepad.exe" in listing.lower():
                running = True
                break
        subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)
        self.assertTrue(running)

    def test_unicode_text_reaches_a_focused_text_field(self):
        import tkinter as tk

        root = tk.Tk()
        self.addCleanup(root.destroy)
        entry = tk.Entry(root, font=("Segoe UI", 16))
        entry.pack()
        root.deiconify()
        entry.focus_force()
        self._pump(root, 1.0)
        self.backend.text("שלום abc")
        self._pump(root, 1.0)
        self.assertEqual(entry.get(), "שלום abc")

    def test_on_screen_keyboard_does_not_take_focus_from_the_app_underneath(self):
        import tkinter as tk

        from xbox_mode.keyboard_model import OnScreenKeyboard
        from xbox_mode.overlay import Overlay

        root = tk.Tk()
        self.addCleanup(root.destroy)
        entry = tk.Entry(root, font=("Segoe UI", 16))
        entry.pack()
        root.deiconify()
        entry.focus_force()
        self._pump(root, 1.0)
        user32 = ctypes.WinDLL("user32")
        before = user32.GetForegroundWindow()

        overlay = Overlay()
        keyboard = OnScreenKeyboard()
        keyboard.toggle()
        overlay.sync(launcher=_EmptyLauncher(), on_screen=keyboard)
        self._pump(root, 1.0)
        self.assertTrue(overlay._keyboard_view._shown)
        self.assertEqual(user32.GetForegroundWindow(), before)
        overlay.close()

    def _pump(self, root, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.05)

    def test_engine_moves_the_real_cursor_right_with_the_stick(self):
        from xbox_mode.controller import ControllerState

        engine = _engine(self.backend)
        before = _cursor()
        now = time.monotonic()
        for _ in range(40):
            engine.step(ControllerState(left=(1.0, 0.0)), now)
            now += 1 / 120
            time.sleep(1 / 120)
        after = _cursor()
        self.assertGreater(after[0] - before[0], 20)

    def test_pygame_source_without_a_controller_reads_none(self):
        import pygame

        from xbox_mode.config import load_config
        from xbox_mode.pygame_source import PygameSource

        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count():
            self.skipTest("a controller is connected, so the source is expected to read it")
        self.assertIsNone(PygameSource(load_config(None)).read())

    def test_overlay_shows_and_hides_the_launcher(self):
        from xbox_mode.keyboard_model import OnScreenKeyboard
        from xbox_mode.launcher import Launcher
        from xbox_mode.launcher_apps import App
        from xbox_mode.overlay import Overlay

        overlay = Overlay()
        keyboard = OnScreenKeyboard()
        launcher = Launcher([App("Notepad", path="a"), App("Calc", path="b")], columns=2)
        launcher.toggle()
        overlay.sync(launcher, keyboard)
        self.assertTrue(overlay._launcher_view._visible)
        launcher.close()
        overlay.sync(launcher, keyboard)
        self.assertFalse(overlay._launcher_view._visible)
        overlay.close()

    def test_taskbar_hides_and_comes_back(self):
        from xbox_mode.taskbar import Taskbar, taskbar_handles, _user32

        user32 = _user32()
        handles = taskbar_handles()
        self.assertTrue(handles, "the taskbar window should be found")
        taskbar = Taskbar()
        self.addCleanup(taskbar.restore)
        taskbar.hide()
        time.sleep(0.5)
        self.assertFalse(any(user32.IsWindowVisible(hwnd) for hwnd in handles))
        taskbar.restore()
        time.sleep(0.5)
        self.assertTrue(all(user32.IsWindowVisible(hwnd) for hwnd in handles))

    def test_open_windows_are_listed(self):
        from xbox_mode.windows_list import list_windows

        self.assertTrue(list_windows(), "at least one app window should be open on the desktop")


class _EmptyLauncher:
    open = False

    def tiles(self):
        return ()


if __name__ == "__main__":
    unittest.main()
