"""THZ Number Entity Platform.

This module provides number entities for configuring THZ heat pump values.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up THZ number entities from a config entry.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry being set up.
        async_add_entities: Callback to add entities.
    """
    entities: list[THZNumber] = []
    write_manager: RegisterMapManagerWrite = hass.data[DOMAIN]["write_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]
    write_registers = write_manager.get_all_registers()

    _LOGGER.debug("write_registers: %s", write_registers)

    for name, entry in write_registers.items():
        if entry["type"] == "number":
            _LOGGER.debug(
                "Creating THZNumber for %s with command %s", name, entry["command"]
            )
            entity = THZNumber(
                name=name,
                command=entry["command"],
                min_value=entry["min"],
                max_value=entry["max"],
                step=entry.get("step", 1),
                unit=entry.get("unit", ""),
                device_class=entry.get("device_class"),
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)

    async_add_entities(entities)
class THZNumber(NumberEntity):
    """Representation of a THZ Number entity.

    This entity allows reading and writing numeric values to the THZ heat pump.

    Attributes:
        _attr_has_entity_name: Indicates the entity has a name.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        command: str,
        min_value: float | str,
        max_value: float | str,
        step: float | str,
        unit: str,
        device_class: str | None,
        device: THZDevice,
        icon: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the THZ Number entity.

        Args:
            name: Entity name.
            command: Command hex string for device communication.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
            step: Step size for value changes.
            unit: Unit of measurement.
            device_class: Device class for the entity.
            device: The THZ device instance.
            icon: Optional icon override.
            unique_id: Optional unique ID override.
        """
        self._attr_name = name
        self._command = command
        self._attr_native_min_value = float(min_value) if min_value != "" else None
        self._attr_native_max_value = float(max_value) if max_value != "" else None
        self._attr_native_step = float(step) if step != "" else 1.0
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._device = device
        self._attr_icon = icon or "mdi:eye"
        self._attr_unique_id = (
            unique_id or f"thz_set_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._attr_native_value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return the native value of the number."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Fetch new state data for the number."""
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                4,
                2,
            )
        value = int.from_bytes(value_bytes, byteorder="big", signed=False)
        self._attr_native_value = value * (self._attr_native_step or 1.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value for the number.

        Args:
            value: The new value to set.
        """
        value_int = int(value / (self._attr_native_step or 1.0))
        value_bytes = value_int.to_bytes(2, byteorder="big", signed=False)
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_bytes,
            )
        self._attr_native_value = value