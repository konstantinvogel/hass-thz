"""THZ Switch Entity Platform.

This module provides switch entities for controlling THZ heat pump functions.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ switch entities from a config entry.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry being set up.
        async_add_entities: Callback to add entities.
    """
    entities: list[THZSwitch] = []
    write_manager: RegisterMapManagerWrite = hass.data[DOMAIN]["write_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]
    write_registers = write_manager.get_all_registers()

    _LOGGER.debug("write_registers: %s", write_registers)

    for name, entry in write_registers.items():
        if entry["type"] == "switch":
            _LOGGER.debug(
                "Creating Switch for %s with command %s", name, entry["command"]
            )
            entity = THZSwitch(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)

    async_add_entities(entities, True)


class THZSwitch(SwitchEntity):
    """Representation of a THZ Switch entity.

    This entity allows controlling on/off functions of the THZ heat pump.

    Attributes:
        _attr_should_poll: Whether the entity should be polled for updates.
        _attr_has_entity_name: Indicates the entity has a name.
    """

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        command: str,
        device: THZDevice,
        icon: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the THZ Switch entity.

        Args:
            name: Entity name.
            command: Command hex string for device communication.
            device: The THZ device instance.
            icon: Optional icon override.
            unique_id: Optional unique ID override.
        """
        self._attr_name = name
        self._command = command
        self._device = device
        self._attr_icon = icon or "mdi:toggle-switch"
        self._attr_unique_id = (
            unique_id or f"thz_switch_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, getattr(self._device, 'unique_id', None) or 'thz_device')},
            name="THZ Wärmepumpe",
            manufacturer="Stiebel Eltron / Tecalor",
            model="THZ",
            sw_version=self._device.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return whether the switch is currently on."""
        return self._is_on

    async def async_update(self) -> None:
        """Fetch new state data for the switch."""
        _LOGGER.debug("Updating switch %s with command %s", self._attr_name, self._command)
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                4,
                2,
            )
            await asyncio.sleep(0.01)
        value = int.from_bytes(value_bytes, byteorder="big", signed=False)
        self._is_on = bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch.

        Args:
            **kwargs: Additional keyword arguments (not used).
        """
        value_bytes = (1).to_bytes(2, byteorder="big", signed=False)
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_bytes,
            )
        self._is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch.

        Args:
            **kwargs: Additional keyword arguments (not used).
        """
        value_bytes = (0).to_bytes(2, byteorder="big", signed=False)
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_bytes,
            )
        self._is_on = False
        self._is_on = False