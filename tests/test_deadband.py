"""Tests for the deadband decision. Run: python3 -m unittest discover -s tests

deadband.py has no Home Assistant imports, so it is loaded straight from its
file and these run without Home Assistant installed.
"""

import importlib.util
from pathlib import Path
import unittest

_PATH = Path(__file__).parent.parent / "custom_components" / "thermobeacon2" / "deadband.py"
_spec = importlib.util.spec_from_file_location("thermobeacon2_deadband", _PATH)
deadband = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deadband)


def update(shown, value, min_change=0.5, available=True, was_available=True, step=None):
    return deadband.should_update(
        shown=shown,
        value=value,
        min_change=min_change,
        available=available,
        was_available=was_available,
        step=step,
    )


class ShouldUpdateTest(unittest.TestCase):
    def test_first_value(self):
        self.assertTrue(update(None, 21.5))

    def test_below_threshold(self):
        self.assertFalse(update(21.5, 21.5))
        self.assertFalse(update(21.5, 21.5625, min_change=0.1))  # one 1/16 degree step
        self.assertFalse(update(48.0, 47.5625))

    def test_at_and_above_threshold(self):
        self.assertTrue(update(48.0, 48.5))
        self.assertTrue(update(48.0, 47.5))
        self.assertTrue(update(21.5, 21.625, min_change=0.1))  # two 1/16 degree steps
        self.assertTrue(update(-60, -63, min_change=3))

    def test_zero_threshold_always_updates(self):
        self.assertTrue(update(21.5, 21.5, min_change=0))

    def test_availability_flip(self):
        self.assertTrue(update(21.5, 21.5, available=False, was_available=True))
        self.assertTrue(update(21.5, 21.5, available=True, was_available=False))

    def test_none_value(self):
        self.assertTrue(update(21.5, None))
        self.assertTrue(update(None, None))

    def test_voltage_boundary_is_exact_in_millivolts(self):
        # As plain floats 2.877 - 2.857 is just under 0.02 and would be dropped.
        self.assertLess(abs(2.877 - 2.857), 0.02)
        self.assertTrue(update(2.857, 2.877, min_change=0.02, step=0.001))
        self.assertTrue(update(2.877, 2.857, min_change=0.02, step=0.001))
        self.assertTrue(update(3.05, 3.03, min_change=0.02, step=0.001))
        self.assertFalse(update(3.05, 3.031, min_change=0.02, step=0.001))
        self.assertFalse(update(3.05, 3.05, min_change=0.02, step=0.001))

if __name__ == "__main__":
    unittest.main()
