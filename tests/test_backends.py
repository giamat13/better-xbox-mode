import ctypes
import os
import sys
import time
import unittest

from xbox_mode.outputs import KEY_NAMES, MOUSE_BUTTONS


class WinBackendLayoutTests(unittest.TestCase):
    """Checks the SendInput structures without calling into Windows."""

    @classmethod
    def setUpClass(cls):
        from xbox_mode import backend_win

        cls.win = backend_win

    def test_every_key_name_has_a_scan_code(self):
        self.assertEqual(set(self.win.SCANCODES), set(KEY_NAMES))

    def test_every_mouse_button_has_flags(self):
        self.assertEqual(set(self.win.BUTTON_FLAGS), set(MOUSE_BUTTONS))

    def test_input_struct_matches_win64_layout(self):
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("Win64 layout only")
        self.assertEqual(ctypes.sizeof(self.win.INPUT), 40)
        self.assertEqual(ctypes.sizeof(self.win.MOUSEINPUT), 32)
        self.assertEqual(ctypes.sizeof(self.win.KEYBDINPUT), 24)

    def test_extended_keys_are_the_arrows_and_paging_keys(self):
        extended = {name for name, (_, flag) in self.win.SCANCODES.items() if flag}
        self.assertEqual(extended, {"up", "down", "left", "right", "pageup", "pagedown"})


@unittest.skipUnless(sys.platform.startswith("linux") and os.environ.get("DISPLAY"),
                     "needs an X display (run under xvfb-run or with DISPLAY set)")
class XTestBackendTests(unittest.TestCase):
    def test_relative_move_changes_real_pointer_position(self):
        from Xlib import display

        from xbox_mode.backend_xtest import XTestBackend

        backend = XTestBackend()
        root = display.Display().screen().root
        start = root.query_pointer()
        backend.move_relative(37, -23)
        time.sleep(0.05)
        end = root.query_pointer()
        self.assertEqual((end.root_x - start.root_x, end.root_y - start.root_y), (37, -23))


if __name__ == "__main__":
    unittest.main()
