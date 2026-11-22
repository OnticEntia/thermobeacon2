"""ThermoBeacon2 BLE hygrometers."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .parser import ThermoBeacon2Reading, parse

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type ThermoBeacon2ConfigEntry = ConfigEntry[ThermoBeacon2Device]


class ThermoBeacon2Device:
    """Holds the latest reading for one sensor and notifies its entities."""

    def __init__(self, address: str) -> None:
        self.address = address
        self.reading: ThermoBeacon2Reading | None = None
        self.rssi: int | None = None
        self.available = False
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange | None = None,
    ) -> None:
        reading = parse(service_info.address, service_info.manufacturer_data)
        if reading is None:
            return
        self.reading = reading
        self.rssi = service_info.rssi
        self.available = True
        self._notify()

    @callback
    def handle_unavailable(self, service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        _LOGGER.debug("%s is no longer seen", self.address)
        self.available = False
        self._notify()


async def async_setup_entry(hass: HomeAssistant, entry: ThermoBeacon2ConfigEntry) -> bool:
    address: str = entry.unique_id
    device = ThermoBeacon2Device(address)
    entry.runtime_data = device

    # Seed with the last advertisement HA already has, so sensors have a value
    # right away instead of waiting for the next broadcast.
    if last := bluetooth.async_last_service_info(hass, address, connectable=False):
        device.handle_advertisement(last)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            device.handle_advertisement,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=False),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass, device.handle_unavailable, address, connectable=False
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermoBeacon2ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
