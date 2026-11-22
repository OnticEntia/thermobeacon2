"""Decide whether a new sensor value is worth writing to Home Assistant.

The sensors broadcast every few seconds and the last digit flickers. Writing
every broadcast would put thousands of meaningless rows a day in the history,
so a value is only written once it has moved far enough from the shown one.

No Home Assistant imports, so this can be tested on its own.
"""

from __future__ import annotations


def should_update(
    *,
    shown: float | int | None,
    value: float | int | None,
    min_change: float,
    available: bool,
    was_available: bool,
    step: float | None = None,
) -> bool:
    """Return True if the entity's state should be written.

    shown          the value currently shown, None if there is none yet
    value          the value just received, None if there is none
    min_change     write once the value is at least this far from `shown`
    available /    availability now and when the state was last written; a
    was_available  change is always written
    step           the value's smallest unit (0.001 for volts counted in mV).
                   When given, the comparison is done in whole steps, so a
                   change of exactly `min_change` is never lost to float
                   rounding (2.877 - 2.857 is 0.01999... as floats).
    """
    if available != was_available:
        return True
    if value is None or shown is None:
        return True
    if step:
        return abs(round(value / step) - round(shown / step)) >= round(min_change / step)
    return abs(value - shown) >= min_change
