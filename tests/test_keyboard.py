import unittest
from typing import List, Tuple

from xbox_mode.config import load_config
from xbox_mode.controller import ControllerState
from xbox_mode.engine import Engine
from xbox_mode.keyboard_model import OnScreenKeyboard
from xbox_mode.launcher import Launcher
from xbox_mode.outputs import KeyboardOutput, MouseOutput
from xbox_mode.policy import EmulationPolicy

TICK = 1.0 / 120


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: List[Tuple] = []

    def move_relative(self, dx, dy):
        self.calls.append(("move", dx, dy))

    def button(self, name, down):
        self.calls.append(("button", name, down))

    def wheel(self, ticks):
        self.calls.append(("wheel", ticks))

    def key(self, name, down):
        self.calls.append(("key", name, down))


class KeyboardModelTests(unittest.TestCase):
    def test_starts_closed_with_the_first_key_selected(self):
        keyboard = OnScreenKeyboard()
        self.assertFalse(keyboard.open)
        self.assertEqual(keyboard.selected().value, "1")

    def test_toggle_opens_and_closes(self):
        keyboard = OnScreenKeyboard()
        self.assertTrue(keyboard.toggle())
        self.assertFalse(keyboard.toggle())

    def test_move_clamps_at_the_edges(self):
        keyboard = OnScreenKeyboard()
        keyboard.move(-1, 0)
        keyboard.move(0, -1)
        self.assertEqual(keyboard.selection(), (0, 0))
        for _ in range(20):
            keyboard.move(1, 0)
        self.assertEqual(keyboard.selected().value, "0")

    def test_moving_down_keeps_the_column_when_the_row_is_long_enough(self):
        keyboard = OnScreenKeyboard()
        keyboard.move(2, 0)
        keyboard.move(0, 1)
        self.assertEqual(keyboard.selected().value, "e")

    def test_pressing_a_letter_returns_it_for_typing(self):
        keyboard = OnScreenKeyboard()
        keyboard.move(0, 1)
        key = keyboard.press()
        self.assertEqual((key.action, key.value), ("text", "q"))

    def test_language_key_switches_layout_and_types_nothing(self):
        keyboard = OnScreenKeyboard()
        keyboard.move(0, 4)
        self.assertEqual(keyboard.selected().action, "lang")
        self.assertIsNone(keyboard.press())
        self.assertEqual(keyboard.language, "he")
        keyboard.move(0, -4)
        self.assertEqual(keyboard.selected().value, "1")
        keyboard.move(0, 1)
        self.assertEqual(keyboard.selected().value, "/")

    def test_hebrew_layout_types_hebrew_letters(self):
        keyboard = OnScreenKeyboard()
        keyboard.language = "he"
        keyboard.move(0, 2)
        self.assertEqual(keyboard.press().value, "ש")

    def test_control_row_has_space_backspace_and_enter(self):
        keyboard = OnScreenKeyboard()
        keyboard.move(0, 4)
        keyboard.move(1, 0)
        self.assertEqual(keyboard.press().action, "space")
        keyboard.move(1, 0)
        self.assertEqual(keyboard.press().action, "backspace")
        keyboard.move(1, 0)
        self.assertEqual(keyboard.press().action, "enter")


class EngineKeyboardRoutingTests(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingBackend()
        self.typed: List[str] = []
        self.on_screen = OnScreenKeyboard()
        config = load_config(None)
        self.engine = Engine(
            config=config,
            mouse=MouseOutput(self.backend),
            keyboard=KeyboardOutput(self.backend),
            launcher=Launcher([]),
            policy=EmulationPolicy({}, 1.0),
            foreground=lambda: (None, "notepad.exe"),
            uses_gamepad=lambda pid, now: False,
            heartbeat=lambda: None,
            toggle_osk=self.on_screen.toggle,
            launch_app=lambda app: None,
            on_screen=self.on_screen,
            type_text=self.typed.append,
        )
        self.now = 0.0

    def tick(self, state):
        self.engine.step(state, self.now)
        self.now += TICK

    def test_y_opens_the_keyboard_and_the_stick_no_longer_moves_the_mouse(self):
        self.tick(ControllerState(buttons=frozenset({"Y"})))
        self.assertTrue(self.on_screen.open)
        self.backend.calls.clear()
        for _ in range(60):
            self.tick(ControllerState(left=(1.0, 0.0)))
        self.assertEqual([call for call in self.backend.calls if call[0] == "move"], [])

    def test_a_types_the_selected_letter(self):
        self.on_screen.toggle()
        self.tick(ControllerState(dpad=(1, 0)))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"A"})))
        self.tick(ControllerState())
        self.assertEqual(self.typed, ["2"])

    def test_dpad_down_then_a_types_from_the_second_row(self):
        self.on_screen.toggle()
        self.tick(ControllerState(dpad=(0, 1)))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"A"})))
        self.tick(ControllerState())
        self.assertEqual(self.typed, ["q"])

    def test_x_sends_backspace_and_start_sends_enter(self):
        self.on_screen.toggle()
        self.tick(ControllerState(buttons=frozenset({"X"})))
        self.tick(ControllerState())
        self.tick(ControllerState(buttons=frozenset({"START"})))
        self.tick(ControllerState())
        keys = [call[1] for call in self.backend.calls if call[0] == "key" and call[2]]
        self.assertEqual(keys, ["backspace", "enter"])

    def test_b_and_y_close_the_keyboard(self):
        self.on_screen.toggle()
        self.tick(ControllerState(buttons=frozenset({"B"})))
        self.tick(ControllerState())
        self.assertFalse(self.on_screen.open)
        self.on_screen.toggle()
        self.tick(ControllerState(buttons=frozenset({"Y"})))
        self.tick(ControllerState())
        self.assertFalse(self.on_screen.open)


if __name__ == "__main__":
    unittest.main()
