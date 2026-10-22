import unittest
from typing import Dict, List, Optional, Tuple

from xbox_mode.config import load_config
from xbox_mode.controller import ControllerState
from xbox_mode.engine import Engine
from xbox_mode.launcher import Launcher
from xbox_mode.launcher_apps import App
from xbox_mode.outputs import KeyboardOutput, MouseOutput
from xbox_mode.policy import HANDLING, NATIVE, EmulationPolicy, PageReport

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

    def events(self, kind):
        return [call for call in self.calls if call[0] == kind]


class Harness:
    def __init__(self, overrides: Optional[Dict] = None, exe: Optional[str] = "notepad.exe",
                 uses_pad: bool = False, report: Optional[PageReport] = None) -> None:
        self.config = load_config(None)
        self.config.update(overrides or {})
        self.backend = RecordingBackend()
        self.osk_toggles = 0
        self.launched: List[App] = []
        self.report = report
        self.exe = exe
        self.uses_pad = uses_pad
        self.now = 0.0
        self.engine = Engine(
            config=self.config,
            mouse=MouseOutput(self.backend),
            keyboard=KeyboardOutput(self.backend),
            launcher=Launcher(
                [App("Notepad", command=("notepad",)), App("Paint", command=("mspaint",)),
                 App("Calc", command=("calc",))],
                columns=2,
            ),
            policy=EmulationPolicy(self.config["overrides"], self.config["heartbeat_stale_seconds"]),
            foreground=lambda: (1234 if self.exe else None, self.exe),
            uses_gamepad=lambda pid, now: self.uses_pad,
            heartbeat=lambda: self.report,
            toggle_osk=self._toggle_osk,
            launch_app=self.launched.append,
        )

    def _toggle_osk(self):
        self.osk_toggles += 1

    def run(self, state: ControllerState, seconds: float) -> None:
        steps = max(1, round(seconds / TICK))
        for _ in range(steps):
            self.engine.step(state, self.now)
            self.now += TICK

    def tick(self, state: ControllerState) -> None:
        self.engine.step(state, self.now)
        self.now += TICK


def pad(**kwargs) -> ControllerState:
    return ControllerState(**kwargs)


class EngineEmulationTests(unittest.TestCase):
    def test_full_left_stick_moves_cursor_right_at_configured_speed(self):
        h = Harness()
        h.run(pad(left=(1.0, 0.0)), 1.0)
        total_x = sum(c[1] for c in h.backend.events("move"))
        total_y = sum(c[2] for c in h.backend.events("move"))
        self.assertGreater(total_x, 1300)
        self.assertLessEqual(total_x, 1400)
        self.assertEqual(total_y, 0)

    def test_stick_inside_deadzone_does_not_move(self):
        h = Harness()
        h.run(pad(left=(0.05, 0.05)), 1.0)
        self.assertEqual(h.backend.events("move"), [])

    def test_a_button_is_left_click_press_and_release(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"A"})))
        h.tick(pad(buttons=frozenset({"A"})))
        h.tick(pad())
        self.assertEqual(h.backend.events("button"), [("button", "left", True), ("button", "left", False)])

    def test_right_stick_up_scrolls_up(self):
        h = Harness()
        h.run(pad(right=(0.0, -1.0)), 0.5)
        ticks = sum(c[1] for c in h.backend.events("wheel"))
        self.assertGreater(ticks, 0)

    def test_dpad_right_taps_right_arrow_once(self):
        h = Harness()
        h.tick(pad(dpad=(1, 0)))
        h.tick(pad(dpad=(0, 0)))
        self.assertEqual(h.backend.events("key"), [("key", "right", True), ("key", "right", False)])

    def test_start_and_back_send_enter_and_escape(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"START"})))
        h.tick(pad(buttons=frozenset({"BACK"})))
        keys = [c[1] for c in h.backend.events("key") if c[2]]
        self.assertEqual(keys, ["enter", "escape"])

    def test_y_toggles_on_screen_keyboard_once_per_press(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"Y"})))
        h.tick(pad(buttons=frozenset({"Y"})))
        h.tick(pad())
        h.tick(pad(buttons=frozenset({"Y"})))
        self.assertEqual(h.osk_toggles, 2)


class EngineGatingTests(unittest.TestCase):
    def test_game_that_loads_a_pad_api_gets_no_emulation(self):
        h = Harness(exe="game.exe", uses_pad=True)
        h.run(pad(left=(1.0, 0.0), buttons=frozenset({"A"})), 0.5)
        self.assertEqual(h.backend.calls, [])

    def test_app_without_pad_api_is_emulated(self):
        h = Harness(exe="writer.exe", uses_pad=False)
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertTrue(h.backend.events("move"))

    def test_chrome_with_fresh_handling_heartbeat_is_left_to_extension(self):
        h = Harness(exe="chrome.exe", report=PageReport(HANDLING, received_at=0.0))
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertEqual(h.backend.calls, [])

    def test_chrome_on_native_gamepad_page_is_passed_through(self):
        h = Harness(exe="chrome.exe", report=PageReport(NATIVE, received_at=0.0))
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertEqual(h.backend.calls, [])

    def test_chrome_without_extension_heartbeat_is_emulated(self):
        h = Harness(exe="chrome.exe", report=None)
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertTrue(h.backend.events("move"))

    def test_override_forces_emulation_for_a_game(self):
        h = Harness(overrides={"overrides": {"game.exe": "emulate"}}, exe="game.exe", uses_pad=True)
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertTrue(h.backend.events("move"))

    def test_override_forces_pass_through(self):
        h = Harness(overrides={"overrides": {"notepad.exe": "pass_through"}}, exe="notepad.exe", uses_pad=False)
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertEqual(h.backend.calls, [])

    def test_pause_releases_a_held_button(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"A"})))
        h.exe = "game.exe"
        h.uses_pad = True
        h.now += 1.0
        h.tick(pad(buttons=frozenset({"A"})))
        self.assertIn(("button", "left", False), h.backend.calls)


class EngineChordAndLauncherTests(unittest.TestCase):
    def test_lb_rb_held_for_a_second_toggles_emulation_off_and_on(self):
        h = Harness()
        chord = frozenset({"LB", "RB"})
        h.run(pad(buttons=chord), 1.2)
        self.assertFalse(h.engine.enabled)
        h.backend.calls.clear()
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertEqual(h.backend.calls, [])
        h.run(pad(buttons=chord), 1.2)
        self.assertTrue(h.engine.enabled)

    def test_guide_opens_launcher_and_dpad_moves_selection(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"GUIDE"})))
        self.assertTrue(h.engine.launcher.open)
        h.tick(pad(dpad=(0, 1)))
        h.tick(pad())
        self.assertEqual(h.launched, [])
        h.tick(pad(buttons=frozenset({"A"})))
        self.assertEqual([app.name for app in h.launched], ["Calc"])
        self.assertFalse(h.engine.launcher.open)

    def test_b_closes_launcher_without_launching(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"GUIDE"})))
        h.tick(pad())
        h.tick(pad(buttons=frozenset({"B"})))
        self.assertFalse(h.engine.launcher.open)
        self.assertEqual(h.launched, [])

    def test_stick_does_not_move_cursor_while_launcher_is_open(self):
        h = Harness()
        h.tick(pad(buttons=frozenset({"GUIDE"})))
        h.run(pad(left=(1.0, 0.0)), 0.5)
        self.assertEqual(h.backend.events("move"), [])


class EngineBindingValidationTests(unittest.TestCase):
    def test_bad_binding_is_rejected_at_startup(self):
        with self.assertRaises(ValueError):
            Harness(overrides={"bindings": {"A": "mouse:thumb"}})

    def test_custom_binding_replaces_default(self):
        h = Harness(overrides={"bindings": {"A": "mouse:right"}})
        h.tick(pad(buttons=frozenset({"A"})))
        self.assertIn(("button", "right", True), h.backend.calls)


if __name__ == "__main__":
    unittest.main()
