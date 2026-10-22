import unittest
from typing import List, Tuple

from xbox_mode.outputs import DpadRepeater, KeyboardOutput, MouseOutput


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


class MouseOutputTests(unittest.TestCase):
    def test_subpixel_movement_accumulates_without_loss(self):
        backend = RecordingBackend()
        mouse = MouseOutput(backend)
        for _ in range(1000):
            mouse.move(0.3, 0.0)
        total = sum(call[1] for call in backend.calls if call[0] == "move")
        self.assertEqual(total, 300)

    def test_negative_subpixel_movement_stays_within_half_a_pixel(self):
        backend = RecordingBackend()
        mouse = MouseOutput(backend)
        for _ in range(10):
            mouse.move(-0.25, 0.0)
        total = sum(call[1] for call in backend.calls if call[0] == "move")
        self.assertLessEqual(abs(total - (-2.5)), 0.5)

    def test_no_backend_call_for_tiny_movement(self):
        backend = RecordingBackend()
        MouseOutput(backend).move(0.2, 0.2)
        self.assertEqual(backend.calls, [])

    def test_press_and_release_send_edges_once(self):
        backend = RecordingBackend()
        mouse = MouseOutput(backend)
        mouse.press("left")
        mouse.press("left")
        mouse.release("left")
        mouse.release("left")
        self.assertEqual(backend.calls, [("button", "left", True), ("button", "left", False)])

    def test_release_all_releases_held_buttons(self):
        backend = RecordingBackend()
        mouse = MouseOutput(backend)
        mouse.press("left")
        mouse.press("right")
        backend.calls.clear()
        mouse.release_all()
        self.assertEqual(sorted(backend.calls), [("button", "left", False), ("button", "right", False)])

    def test_scroll_accumulates_whole_ticks(self):
        backend = RecordingBackend()
        mouse = MouseOutput(backend)
        for _ in range(4):
            mouse.scroll(0.5)
        self.assertEqual([c for c in backend.calls if c[0] == "wheel"], [("wheel", 1), ("wheel", 1)])

    def test_unknown_button_is_rejected(self):
        with self.assertRaises(ValueError):
            MouseOutput(RecordingBackend()).press("thumb")


class KeyboardOutputTests(unittest.TestCase):
    def test_tap_sends_down_then_up(self):
        backend = RecordingBackend()
        KeyboardOutput(backend).tap("enter")
        self.assertEqual(backend.calls, [("key", "enter", True), ("key", "enter", False)])

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(ValueError):
            KeyboardOutput(RecordingBackend()).tap("f13")

    def test_release_all_releases_held_keys(self):
        backend = RecordingBackend()
        keyboard = KeyboardOutput(backend)
        keyboard.press("up")
        backend.calls.clear()
        keyboard.release_all()
        self.assertEqual(backend.calls, [("key", "up", False)])


class DpadRepeaterTests(unittest.TestCase):
    def test_single_press_emits_once_immediately(self):
        repeater = DpadRepeater(delay=0.4, interval=0.1)
        self.assertEqual(repeater.update((0, -1), 0.0), [(0, -1)])
        self.assertEqual(repeater.update((0, 0), 0.05), [])

    def test_hold_repeats_after_delay_at_interval(self):
        repeater = DpadRepeater(delay=0.4, interval=0.1)
        emitted = []
        t = 0.0
        emitted += repeater.update((1, 0), t)
        while t < 1.0:
            t += 0.01
            emitted += [(t, step) for step in repeater.update((1, 0), t)]
        times = [when for when, _ in emitted[1:]]
        self.assertGreaterEqual(times[0], 0.4 - 1e-9)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(0.09 <= gap <= 0.12 for gap in gaps), gaps)

    def test_diagonal_is_ignored(self):
        repeater = DpadRepeater(delay=0.4, interval=0.1)
        self.assertEqual(repeater.update((1, 1), 0.0), [])


if __name__ == "__main__":
    unittest.main()
