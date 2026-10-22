"""Full input chain on Windows with a virtual Xbox 360 pad (ViGEmBus + vgamepad). Skipped without them.

Chain under test: virtual pad -> pygame joystick -> PygameSource -> Engine -> SendInput -> real cursor.
"""
import sys
import time
import unittest

WINDOWS = sys.platform == "win32"


def _cursor():
    import ctypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = POINT()
    ctypes.WinDLL("user32").GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _set_cursor(x, y):
    import ctypes

    ctypes.WinDLL("user32").SetCursorPos(int(x), int(y))


@unittest.skipUnless(WINDOWS, "Windows only")
class VirtualControllerTests(unittest.TestCase):
    def setUp(self):
        try:
            import vgamepad
        except ImportError:
            self.skipTest("vgamepad is not installed")
        self.vg = vgamepad

    def _read_until_connected(self, source, pad, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pad.update()
            state = source.read()
            if state is not None:
                return state
            time.sleep(0.2)
        return None

    def test_virtual_pad_stick_moves_the_real_cursor_through_the_whole_chain(self):
        from xbox_mode.backend_win import WinInputBackend
        from xbox_mode.config import load_config
        from xbox_mode.engine import Engine
        from xbox_mode.launcher import Launcher
        from xbox_mode.outputs import KeyboardOutput, MouseOutput
        from xbox_mode.policy import EmulationPolicy
        from xbox_mode.pygame_source import PygameSource

        config = load_config(None)
        pad = self.vg.VX360Gamepad()
        self.addCleanup(lambda: pad.reset() or pad.update())
        source = PygameSource(config)
        self.assertIsNotNone(self._read_until_connected(source, pad), "pygame never saw the virtual pad")

        backend = WinInputBackend()
        engine = Engine(
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

        _set_cursor(400, 400)
        time.sleep(0.1)
        before = _cursor()
        pad.left_joystick_float(x_value_float=1.0, y_value_float=0.0)
        pad.update()
        now = time.monotonic()
        seen_x = 0.0
        for _ in range(120):
            state = source.read()
            if state is not None:
                seen_x = max(seen_x, state.left[0])
                engine.step(state, now)
            now += 1 / 120
            time.sleep(1 / 120)
        pad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
        pad.update()
        after = _cursor()

        self.assertGreater(seen_x, 0.8, "pygame should report the stick deflection")
        self.assertGreater(after[0] - before[0], 50, f"cursor moved from {before} to {after}")

    def test_virtual_pad_button_a_reaches_pygame_state(self):
        from xbox_mode.config import load_config
        from xbox_mode.pygame_source import PygameSource

        config = load_config(None)
        pad = self.vg.VX360Gamepad()
        self.addCleanup(lambda: pad.reset() or pad.update())
        source = PygameSource(config)
        self.assertIsNotNone(self._read_until_connected(source, pad))

        pad.press_button(button=self.vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        pad.update()
        pressed = False
        for _ in range(30):
            time.sleep(0.05)
            state = source.read()
            if state is not None and "A" in state.buttons:
                pressed = True
                break
        pad.release_button(button=self.vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        pad.update()
        self.assertTrue(pressed, "button A should map to the A entry in joystick_buttons")


if __name__ == "__main__":
    unittest.main()
