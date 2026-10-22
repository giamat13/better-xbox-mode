import math
import unittest

from xbox_mode.mapping import ButtonEdges, ChordTimer, shape_stick


class ShapeStickTests(unittest.TestCase):
    def test_inside_deadzone_is_zero(self):
        self.assertEqual(shape_stick(0.05, -0.05, deadzone=0.12, exponent=2.0), (0.0, 0.0))

    def test_full_deflection_is_unit_length(self):
        x, y = shape_stick(1.0, 0.0, deadzone=0.12, exponent=2.0)
        self.assertAlmostEqual(x, 1.0)
        self.assertAlmostEqual(y, 0.0)

    def test_diagonal_is_clamped_to_unit_circle(self):
        x, y = shape_stick(1.0, 1.0, deadzone=0.12, exponent=2.0)
        self.assertAlmostEqual(math.hypot(x, y), 1.0)
        self.assertAlmostEqual(x, y)

    def test_just_outside_deadzone_starts_at_zero_without_a_jump(self):
        x, _ = shape_stick(0.1201, 0.0, deadzone=0.12, exponent=1.0)
        self.assertLess(x, 0.001)

    def test_direction_is_preserved(self):
        x, y = shape_stick(0.3, -0.4, deadzone=0.1, exponent=2.0)
        self.assertLess(y, 0)
        self.assertGreater(x, 0)
        self.assertAlmostEqual(x / y, 0.3 / -0.4)

    def test_exponent_reduces_mid_deflection(self):
        linear, _ = shape_stick(0.5, 0.0, deadzone=0.0, exponent=1.0)
        curved, _ = shape_stick(0.5, 0.0, deadzone=0.0, exponent=2.0)
        self.assertAlmostEqual(linear, 0.5)
        self.assertAlmostEqual(curved, 0.25)

    def test_zero_deadzone_zero_input_does_not_divide_by_zero(self):
        self.assertEqual(shape_stick(0.0, 0.0, deadzone=0.0, exponent=2.0), (0.0, 0.0))


class ButtonEdgesTests(unittest.TestCase):
    def test_press_then_release(self):
        edges = ButtonEdges()
        self.assertEqual(edges.update(frozenset({"A"})), (frozenset({"A"}), frozenset()))
        self.assertEqual(edges.update(frozenset({"A"})), (frozenset(), frozenset()))
        self.assertEqual(edges.update(frozenset()), (frozenset(), frozenset({"A"})))


class ChordTimerTests(unittest.TestCase):
    def test_fires_once_after_hold(self):
        chord = ChordTimer(("LB", "RB"), hold_seconds=1.0)
        held = frozenset({"LB", "RB"})
        self.assertFalse(chord.update(held, 0.0))
        self.assertFalse(chord.update(held, 0.5))
        self.assertTrue(chord.update(held, 1.0))
        self.assertFalse(chord.update(held, 1.5))

    def test_release_resets_and_can_fire_again(self):
        chord = ChordTimer(("LB", "RB"), hold_seconds=1.0)
        held = frozenset({"LB", "RB"})
        chord.update(held, 0.0)
        self.assertTrue(chord.update(held, 1.0))
        chord.update(frozenset(), 1.1)
        chord.update(held, 2.0)
        self.assertTrue(chord.update(held, 3.0))

    def test_partial_chord_never_fires(self):
        chord = ChordTimer(("LB", "RB"), hold_seconds=1.0)
        for t in range(0, 30):
            self.assertFalse(chord.update(frozenset({"LB"}), t * 0.1))


if __name__ == "__main__":
    unittest.main()
