"""Full input chain on Windows with a vJoy virtual joystick. Skipped where vJoy is not installed.

Chain under test: vJoy device -> pygame joystick -> PygameSource -> Engine -> SendInput -> real cursor.
The default config already matches vJoy: axis 0 is X, axis 1 is Y, and button 1 is A.
"""
import ctypes
import os
import sys
import time
import unittest

WINDOWS = sys.platform == "win32"
VJOY_DLL = r"C:\Program Files\vJoy\x64\vJoyInterface.dll"
DEVICE = 1
HID_USAGE_X = 0x30
AXIS_MIN = 0x0001
AXIS_CENTER = 0x4000
AXIS_MAX = 0x8000


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor():
    point = POINT()
    ctypes.WinDLL("user32").GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _set_cursor(x, y):
    ctypes.WinDLL("user32").SetCursorPos(int(x), int(y))


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


@unittest.skipUnless(WINDOWS and os.path.exists(VJOY_DLL), "needs vJoy installed on Windows")
class VJoyControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vjoy = ctypes.WinDLL(VJOY_DLL)
        vjoy.vJoyEnabled.restype = ctypes.c_bool
        vjoy.GetVJDStatus.argtypes = [ctypes.c_uint]
        vjoy.GetVJDStatus.restype = ctypes.c_int
        vjoy.AcquireVJD.argtypes = [ctypes.c_uint]
        vjoy.AcquireVJD.restype = ctypes.c_bool
        vjoy.RelinquishVJD.argtypes = [ctypes.c_uint]
        vjoy.SetAxis.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_uint]
        vjoy.SetAxis.restype = ctypes.c_bool
        vjoy.SetBtn.argtypes = [ctypes.c_bool, ctypes.c_uint, ctypes.c_ubyte]
        vjoy.SetBtn.restype = ctypes.c_bool
        cls.vjoy = vjoy
        if not vjoy.vJoyEnabled():
            raise AssertionError("vJoy driver is not enabled")
        if not vjoy.AcquireVJD(DEVICE):
            raise AssertionError(f"could not acquire vJoy device {DEVICE}, status {vjoy.GetVJDStatus(DEVICE)}")
        vjoy.SetAxis(AXIS_CENTER, DEVICE, HID_USAGE_X)
        vjoy.SetAxis(AXIS_CENTER, DEVICE, HID_USAGE_X + 1)
        vjoy.SetBtn(False, DEVICE, 1)

    @classmethod
    def tearDownClass(cls):
        cls.vjoy.RelinquishVJD(DEVICE)

    def _source_with_joystick(self, timeout=15.0):
        from xbox_mode.config import load_config
        from xbox_mode.pygame_source import PygameSource

        source = PygameSource(load_config(None))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = source.read()
            if state is not None:
                return source
            time.sleep(0.2)
        self.fail("pygame never reported the vJoy device as a joystick")

    def test_joystick_stick_moves_the_real_cursor_through_vjoy_and_pygame(self):
        from xbox_mode.backend_win import WinInputBackend

        source = self._source_with_joystick()
        engine = _engine(WinInputBackend())
        _set_cursor(400, 400)
        time.sleep(0.1)
        before = _cursor()

        self.vjoy.SetAxis(AXIS_MAX, DEVICE, HID_USAGE_X)
        seen_x = 0.0
        now = time.monotonic()
        for _ in range(120):
            state = source.read()
            if state is not None:
                seen_x = max(seen_x, state.left[0])
                engine.step(state, now)
            now += 1 / 120
            time.sleep(1 / 120)
        self.vjoy.SetAxis(AXIS_CENTER, DEVICE, HID_USAGE_X)
        after = _cursor()

        self.assertGreater(seen_x, 0.8, "pygame should report the vJoy stick at full deflection")
        self.assertGreater(after[0] - before[0], 50, f"cursor moved from {before} to {after}")

    def test_vjoy_button_one_reaches_pygame_state_as_a(self):
        source = self._source_with_joystick()
        self.vjoy.SetBtn(True, DEVICE, 1)
        pressed = False
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            state = source.read()
            if state is not None and "A" in state.buttons:
                pressed = True
                break
            time.sleep(0.05)
        self.vjoy.SetBtn(False, DEVICE, 1)
        self.assertTrue(pressed, "vJoy button 1 should appear as A in the pygame state")


if __name__ == "__main__":
    unittest.main()
