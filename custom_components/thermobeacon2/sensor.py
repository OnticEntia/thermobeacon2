"""Sensors for ThermoBeacon2 hygrometers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThermoBeacon2ConfigEntry, ThermoBeacon2Device
from .const import MANUFACTURER, MODEL
from .deadband import should_update


@dataclass(frozen=True, kw_only=True)
class ThermoBeacon2SensorDescription(SensorEntityDescription):
    value_fn: Callable[[ThermoBeacon2Device], float | int | None]
    # A new value is only shown once it differs from the shown one by this
    # much; see deadband.py. `step` is the value's smallest unit, given where
    # the comparison has to be exact.
    min_change: float = 0
    step: float | None = None


SENSORS: tuple[ThermoBeacon2SensorDescription, ...] = (
    ThermoBeacon2SensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        min_change=0.1,
        value_fn=lambda d: d.reading.temperature if d.reading else None,
    ),
    ThermoBeacon2SensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        min_change=0.5,
        value_fn=lambda d: d.reading.humidity if d.reading else None,
    ),
    ThermoBeacon2SensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_change=0.02,
        step=0.001,  # the device reports whole millivolts
        value_fn=lambda d: d.reading.voltage if d.reading else None,
    ),
    ThermoBeacon2SensorDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_change=3,
        value_fn=lambda d: d.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThermoBeacon2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    async_add_entities(ThermoBeacon2Sensor(device, entry.title, desc) for desc in SENSORS)


class ThermoBeacon2Sensor(SensorEntity):
    """One measurement from a ThermoBeacon2."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: ThermoBeacon2SensorDescription

    def __init__(
        self, device: ThermoBeacon2Device, title: str, description: ThermoBeacon2SensorDescription
    ) -> None:
        self._device = device
        self.entity_description = description
        self._shown: float | int | None = None
        self._was_available = False
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{device.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, device.address)},
            name=title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        return self._device.available

    @property
    def native_value(self) -> float | int | None:
        return self._shown

    async def async_added_to_hass(self) -> None:
        self._shown = self.entity_description.value_fn(self._device)
        self._was_available = self._device.available
        self.async_on_remove(self._device.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        value = self.entity_description.value_fn(self._device)
        available = self._device.available
        if not should_update(
            shown=self._shown,
            value=value,
            min_change=self.entity_description.min_change,
            available=available,
            was_available=self._was_available,
            step=self.entity_description.step,
        ):
            return  # nothing worth showing changed
        if value is not None:
            self._shown = value
        self._was_available = available
        self.async_write_ha_state()
