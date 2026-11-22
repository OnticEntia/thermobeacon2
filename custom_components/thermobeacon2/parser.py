"""Parse ThermoBeacon2 BLE advertisements.

These LCD hygrometers advertise as "ThermoBeacon2" with manufacturer id 25
(0x0019) and service UUID 0xFFF0. The 20-byte manufacturer payload is:

    [0:6]   device MAC address, byte-reversed
    [6:8]   battery voltage, mV        (uint16 little-endian)
    [8:10]  temperature, 1/16 degree C (int16 little-endian)
    [10:12] relative humidity, 1/16 %  (uint16 little-endian)
    [12:16] reserved (0xFFFFFFFF)
    [16:20] uptime counter, seconds    (uint32 little-endian)

The older ThermoBeacon models handled by Home Assistant's built-in
`thermobeacon` integration put two flag bytes before the MAC, so its parser
rejects this layout.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

MANUFACTURER_ID = 25
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
PAYLOAD_LENGTH = 20
# In saturated air the sensor can report a little over 100 %. Up to this much
# is shown as 100; anything higher is treated as a corrupt reading.
MAX_HUMIDITY_OVERSHOOT = 105


@dataclass(frozen=True, slots=True)
class ThermoBeacon2Reading:
    """One decoded advertisement."""

    temperature: float  # degrees C
    humidity: float  # percent
    voltage: float  # volts
    uptime: int  # seconds


def parse(address: str, manufacturer_data: dict[int, bytes]) -> ThermoBeacon2Reading | None:
    """Decode a ThermoBeacon2 advertisement, or return None if it isn't one."""
    payload = manufacturer_data.get(MANUFACTURER_ID)
    if payload is None or len(payload) != PAYLOAD_LENGTH:
        return None

    # The payload starts with the device's own MAC, reversed. Checking it
    # guards against other devices that happen to use manufacturer id 25.
    if payload[0:6][::-1].hex(":").upper() != address.upper():
        return None

    volt_mv, temp16, humi16 = struct.unpack_from("<HhH", payload, 6)
    (uptime,) = struct.unpack_from("<I", payload, 16)
    temperature = temp16 / 16
    humidity = humi16 / 16

    if not -40 <= temperature <= 85 or not 0 <= humidity <= MAX_HUMIDITY_OVERSHOOT:
        return None
    humidity = min(humidity, 100.0)

    return ThermoBeacon2Reading(
        temperature=round(temperature, 2),
        humidity=round(humidity, 2),
        voltage=round(volt_mv / 1000, 3),
        uptime=uptime,
    )
