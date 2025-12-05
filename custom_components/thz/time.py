"""Time entity for THZ devices.

This module provides time entities for the THZ heat pump,
allowing configuration of scheduling times in 15-minute intervals.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice


_LOGGER = logging.getLogger(__name__)

# Sentinel value for "no time set" in the THZ protocol
_NO_TIME_SENTINEL = 0x80  # 128


def time_to_quarters(t: time | None) -> int:
    """Convert a time object to the number of 15-minute intervals since midnight.

    The THZ device stores time values as the count of 15-minute intervals
    (quarters) since midnight.

    Args:
        t: The time to convert. If None, returns the sentinel value 128 (0x80).

    Returns:
        The count of 15-minute intervals since midnight:
        - 0 represents 00:00
        - Each hour adds 4 intervals
        - Minutes are floored to the nearest 15-minute boundary
        - Valid values range from 0 to 95 (00:00 through 23:45)
        - 128 is the sentinel for unset/None

    Examples:
        >>> time_to_quarters(time(0, 0))
        0
        >>> time_to_quarters(time(1, 30))
        6
        >>> time_to_quarters(None)
        128
    """
    if t is None:
        return _NO_TIME_SENTINEL
    return t.hour * 4 + (t.minute // 15)


def quarters_to_time(num: int) -> time | None:
    """Convert a count of 15-minute intervals since midnight to a time object.

    Args:
        num: Number of 15-minute intervals (quarters) since midnight.
            Expected range is 0-95 (0 => 00:00, 95 => 23:45).
            The sentinel value 0x80 (128) indicates "no time".

    Returns:
        A time object representing the corresponding hour and minute,
        or None if num equals the sentinel value (0x80).

    Examples:
        >>> quarters_to_time(0)
        datetime.time(0, 0)
        >>> quarters_to_time(1)
        datetime.time(0, 15)
        >>> quarters_to_time(95)
        datetime.time(23, 45)
        >>> quarters_to_time(0x80)
        None
    """
    if num == _NO_TIME_SENTINEL:
        return None
    quarters = num % 4
    hour = (num - quarters) // 4
    return time(hour, quarters * 15)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ Time entities from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: The config entry for this integration.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    entities: list[THZTime] = []
    write_manager: RegisterMapManagerWrite = hass.data["thz"]["write_manager"]
    device: THZDevice = hass.data["thz"]["device"]
    write_registers = write_manager.get_all_registers()

    _LOGGER.debug("write_registers: %s", write_registers)

    for name, entry in write_registers.items():
        if entry["type"] == "time":
            _LOGGER.debug(
                "Creating Time for %s with command %s", name, entry["command"]
            )
            entity = THZTime(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)

    async_add_entities(entities, True)


class THZTime(TimeEntity):
    """Time entity for THZ devices.

    This entity allows setting time values for scheduling functions
    on the THZ heat pump. Times are stored in 15-minute intervals.

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
        """Initialize the THZ Time entity.

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
        self._attr_icon = icon or "mdi:clock"
        self._attr_unique_id = (
            unique_id or f"thz_time_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._attr_native_value: time | None = None

    @property
    def native_value(self) -> time | None:
        """Return the native time value."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Fetch new state data for the time entity."""
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                4,
                2,
            )
            await asyncio.sleep(0.01)

        num = value_bytes[0]
        self._attr_native_value = quarters_to_time(num)

    async def async_set_native_value(self, value: time) -> None:
        """Set new time value.

        Args:
            value: The time value to set.
        """
        num = time_to_quarters(value)
        num_bytes = num.to_bytes(2, byteorder="big", signed=False)

        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                num_bytes,
            )
            await asyncio.sleep(0.01)

        self._attr_native_value = value