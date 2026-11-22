"""Config flow for ThermoBeacon2."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, MODEL
from .parser import parse


def _title(address: str) -> str:
    return f"{MODEL} {address.replace(':', '')[-4:]}"


class ThermoBeacon2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a ThermoBeacon2, from Bluetooth discovery or picked from a list."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: BluetoothServiceInfoBleak | None = None
        self._choices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if parse(discovery_info.address, discovery_info.manufacturer_data) is None:
            return self.async_abort(reason="not_supported")
        self._discovered = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info.address)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovered is not None
        title = _title(self._discovered.address)
        if user_input is not None:
            return self.async_create_entry(title=title, data={})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders={"name": title}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self._choices[address], data={})

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=False):
            if info.address in configured or info.address in self._choices:
                continue
            if parse(info.address, info.manufacturer_data) is not None:
                self._choices[info.address] = _title(info.address)

        if not self._choices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._choices)}),
        )
