import unittest
from typing import List

from xbox_mode.config import load_config
from xbox_mode.controller import ControllerState
from xbox_mode.engine import Engine
from xbox_mode.keyboard_model import OnScreenKeyboard
from xbox_mode.launcher import Launcher
from xbox_mode.outputs import KeyboardOutput, MouseOutput
from xbox_mode.policy import EmulationPolicy
from xbox_mode.switcher import TaskSwitcher
from xbox_mode.windows_list import WindowEntry, filter_windows

TICK = 1.0 / 120


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: List = []

    def move_relative(self, dx, dy):
        self.calls.append(("move", dx, dy))

    def button(self, name, down):
        self.calls.append(("button", name, down))

    def wheel(self, ticks):
        self.calls.append(("wheel", ticks))

    def key(self, name, down):
        self.calls.append(("key", name, down))


def window(hwnd, title, class_name="App"):
    return WindowEntry(hwnd=hwnd, title=title, class_name=class_name)


class FilterWindowsTests(unittest.TestCase):
    def test_skips_empty_titles_shell_windows_and_our_own_window(self):
        entries = [
            window(1, ""),
            window(2, "Program Manager", "Progman"),
            window(3, "Taskbar", "Shell_TrayWnd"),
            window(4, "Xbox mode"),
            window(5, "Notepad", "Notepad"),
        ]
        self.assertEqual([entry.hwnd for entry in filter_windows(entries)], [5])

    def test_keeps_the_order_of_the_remaining_windows(self):
        entries = [window(7, "Chrome"), window(8, "Excel"), window(9, "Calc")]
        self.assertEqual([entry.title for entry in filter_windows(entries)], ["Chrome", "Excel", "Calc"])


class TaskSwitcherTests(unittest.TestCase):
    def setUp(self):
        self.windows = [window(1, "Chrome"), window(2, "Excel"), window(3, "Notepad")]
        self.activated: List[int] = []
        self.closed: List[int] = []
        self.switcher = TaskSwitcher(
            provider=lambda: list(self.windows),
            activate=self.activated.append,
            close=self.closed.append,
        )

    def test_opening_lists_the_windows_and_selects_the_first(self):
        self.assertTrue(self.switcher.toggle())
        self.assertEqual([item.title for item in self.switcher.items], ["Chrome", "Excel", "Notepad"])
        self.assertEqual(self.switcher.selected().title, "Chrome")

    def test_move_clamps_at_both_ends(self):
        self.switcher.toggle()
        self.switcher.move(-1)
        self.assertEqual(self.switcher.index, 0)
        for _ in range(10):
            self.switcher.move(1)
        self.assertEqual(self.switcher.selected().title, "Notepad")

    def test_activate_brings_the_selected_window_forward_and_closes_the_switcher(self):
        self.switcher.toggle()
        self.switcher.move(1)
        self.switcher.activate()
        self.assertEqual(self.activated, [2])
        self.assertFalse(self.switcher.open)

    def test_close_selected_closes_the_window_and_keeps_the_switcher_open(self):
        self.switcher.toggle()
        self.switcher.move(2)
        self.switcher.close_selected()
        self.assertEqual(self.closed, [3])
        self.assertTrue(self.switcher.open)
        self.assertEqual(self.switcher.selected().title, "Excel")

    def test_empty_list_is_safe(self):
        self.windows.clear()
        self.switcher.toggle()
        self.switcher.move(1)
        self.switcher.close_selected()
        self.switcher.activate()
        self.assertIsNone(self.switcher.selected())
        self.assertEqual(self.activated, [])
        self.assertEqual(self.closed, [])


class EngineSwitcherRoutingTests(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingBackend()
        self.activated: List[int] = []
        self.closed: List[int] = []
        self.switcher = TaskSwitcher(
            provider=lambda: [window(1, "Chrome"), window(2, "Excel")],
            activate=self.activated.append,
            close=self.closed.append,
        )
        self.engine = Engine(
            config=load_config(None),
            mouse=MouseOutput(self.backend),
            keyboard=KeyboardOutput(self.backend),
            launcher=Launcher([]),
            policy=EmulationPolicy({}, 1.0),
            foreground=lambda: (None, "notepad.exe"),
            uses_gamepad=lambda pid, now: False,
            heartbeat=lambda: None,
            toggle_osk=lambda: None,
            launch_app=lambda app: None,
            on_screen=OnScreenKeyboard(),
            switcher=self.switcher,
        )
        self.now = 0.0

    def tick(self, state):
        self.engine.step(state, self.now)
        self.now += TICK

    def test_back_opens_the_switcher(self):
        self.tick(ControllerState(buttons=frozenset({"BACK"})))
        self.assertTrue(self.switcher.open)

    def test_rb_then_a_switches_to_the_second_window(self):
        self.tick(ControllerState(buttons=frozenset({"BACK"})))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"RB"})))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"A"})))
        self.assertEqual(self.activated, [2])
        self.assertFalse(self.switcher.open)

    def test_x_closes_the_selected_window(self):
        self.tick(ControllerState(buttons=frozenset({"BACK"})))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"X"})))
        self.assertEqual(self.closed, [1])

    def test_b_leaves_without_switching(self):
        self.tick(ControllerState(buttons=frozenset({"BACK"})))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"B"})))
        self.assertFalse(self.switcher.open)
        self.assertEqual(self.activated, [])

    def test_stick_does_not_move_the_mouse_while_switching(self):
        self.tick(ControllerState(buttons=frozenset({"BACK"})))
        self.backend.calls.clear()
        for _ in range(30):
            self.tick(ControllerState(left=(1.0, 0.0)))
        self.assertEqual([call for call in self.backend.calls if call[0] == "move"], [])


if __name__ == "__main__":
    unittest.main()
