"""Tests for the advertisement parser. Run: python3 -m unittest discover -s tests

The parser has no Home Assistant imports, so it is loaded straight from its
file and these run without Home Assistant installed.
"""

import importlib.util
from pathlib import Path
import struct
import sys
import unittest

_PATH = Path(__file__).parent.parent / "custom_components" / "thermobeacon2" / "parser.py"
_spec = importlib.util.spec_from_file_location("thermobeacon2_parser", _PATH)
parser = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = parser  # dataclasses look the module up by name
_spec.loader.exec_module(parser)

ADDRESS = "AA:BB:CC:DD:EE:01"


def payload(address=ADDRESS, mv=3050, temp16=int(21.5 * 16), humi16=int(48.25 * 16), uptime=123456):
    mac = bytes.fromhex(address.replace(":", ""))[::-1]
    return mac + struct.pack("<HhH", mv, temp16, humi16) + b"\xff\xff\xff\xff" + struct.pack("<I", uptime)


class ParseTest(unittest.TestCase):
    def test_reading(self):
        reading = parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload()})
        self.assertEqual(reading.temperature, 21.5)
        self.assertEqual(reading.humidity, 48.25)
        self.assertEqual(reading.voltage, 3.05)
        self.assertEqual(reading.uptime, 123456)

    def test_below_freezing(self):
        reading = parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(temp16=int(-10.5 * 16))})
        self.assertEqual(reading.temperature, -10.5)

    def test_address_is_case_insensitive(self):
        self.assertIsNotNone(parser.parse(ADDRESS.lower(), {parser.MANUFACTURER_ID: payload()}))

    def test_other_manufacturer(self):
        self.assertIsNone(parser.parse(ADDRESS, {76: payload()}))

    def test_wrong_length(self):
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload()[:-1]}))
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload() + b"\x00"}))

    def test_mac_in_payload_must_match(self):
        other = payload(address="AA:BB:CC:DD:EE:02")
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: other}))

    def test_out_of_range_values(self):
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(temp16=100 * 16)}))
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(temp16=-50 * 16)}))
        self.assertIsNone(parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(humi16=105 * 16 + 1)}))

    def test_humidity_just_over_100_is_clamped(self):
        for humi16 in (100 * 16 + 1, 103 * 16, 105 * 16):
            reading = parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(humi16=humi16)})
            self.assertEqual(reading.humidity, 100)
            self.assertEqual(reading.temperature, 21.5)  # the rest of the reading survives
        exact = parser.parse(ADDRESS, {parser.MANUFACTURER_ID: payload(humi16=100 * 16)})
        self.assertEqual(exact.humidity, 100)


if __name__ == "__main__":
    unittest.main()
