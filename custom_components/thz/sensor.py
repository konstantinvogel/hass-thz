"""THZ Sensor Platform.

This module provides sensor entities for reading values from the THZ heat pump.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .register_maps.register_map_manager import RegisterMapManager
from .sensor_meta import SENSOR_META
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ sensors from a config entry.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry being set up.
        async_add_entities: Callback to add entities.
    """
    register_manager: RegisterMapManager = hass.data[DOMAIN]["register_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]

    sensors: list[THZSensor] = []
    all_registers = register_manager.get_all_registers()

    for block, entries in all_registers.items():
        block_name = block.strip("pxx")
        block_bytes = bytes.fromhex(block_name)

        for name, offset, length, decode_type, factor in entries:
            meta = SENSOR_META.get(name.strip(), {})
            sensor_config = {
                "name": name.strip(),
                "offset": offset // 2,  # Register offset in bytes
                "length": (length + 1) // 2,  # Register length in bytes
                "decode": decode_type,
                "factor": factor,
                "unit": meta.get("unit"),
                "device_class": meta.get("device_class"),
                "icon": meta.get("icon"),
                "translation_key": meta.get("translation_key"),
            }
            sensors.append(
                THZSensor(
                    config=sensor_config,
                    block=block_bytes,
                    device=device,
                )
            )

    async_add_entities(sensors, True)


def decode_value(
    raw: bytes, decode_type: str, factor: float = 1.0
) -> int | float | str:
    """Decode raw bytes to a value based on decode type.

    Args:
        raw: Raw bytes to decode.
        decode_type: Type of decoding to apply.
        factor: Division factor for the result.

    Returns:
        Decoded value (numeric or string).
    """
    if decode_type == "hex2int":
        return int.from_bytes(raw, byteorder="big", signed=True) / factor
    elif decode_type == "hex":
        return int.from_bytes(raw, byteorder="big")
    elif decode_type.startswith("bit"):
        bitnum = int(decode_type[3:])
        return (raw[0] >> bitnum) & 0x01
    elif decode_type.startswith("nbit"):
        bitnum = int(decode_type[4:])
        return int(not ((raw[0] >> bitnum) & 0x01))
    elif decode_type == "esp_mant":
        # Exponential mantissa format
        mant = int.from_bytes(raw[:4], byteorder="big")
        exp = int.from_bytes(raw[4:], byteorder="big")
        return mant * (2**exp)
    else:
        return raw.hex()


def normalize_entry(entry: tuple | dict) -> dict[str, Any]:
    """Normalize sensor entry to dictionary format.

    Args:
        entry: Tuple or dict sensor configuration.

    Returns:
        Normalized dictionary configuration.

    Raises:
        ValueError: If entry format is not supported.
    """
    if isinstance(entry, tuple):
        name, offset, length, decode, factor = entry
        return {
            "name": name.strip(),
            "offset": offset,
            "length": length,
            "decode": decode,
            "factor": factor,
            "unit": None,
            "device_class": None,
            "icon": None,
            "translation_key": None,
        }
    elif isinstance(entry, dict):
        return entry
    else:
        raise ValueError(f"Unsupported sensor entry format: {type(entry)}")

class THZSensor(SensorEntity):
    """Representation of a THZ sensor entity.

    This sensor reads values from the THZ heat pump and decodes them
    according to the specified decode type.

    Attributes:
        _attr_has_entity_name: Indicates the entity has a name.
        _attr_state_class: The state class for the sensor.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config: dict[str, Any],
        block: bytes,
        device: THZDevice,
    ) -> None:
        """Initialize the THZ sensor.

        Args:
            config: Sensor configuration dictionary.
            block: Block address bytes.
            device: The THZ device instance.
        """
        entry = normalize_entry(config)
        self._name = entry["name"]
        self._block = block
        self._offset = entry["offset"]
        self._length = entry["length"]
        self._decode_type = entry["decode"]
        self._factor = entry["factor"]
        self._device = device
        self._state: int | float | str | None = None

        # Entity attributes
        self._attr_name = entry["name"]
        self._attr_native_unit_of_measurement = entry.get("unit")
        self._attr_device_class = entry.get("device_class")
        self._attr_icon = entry.get("icon")
        self._attr_translation_key = entry.get("translation_key")
        self._attr_unique_id = (
            f"thz_{self._block.hex()}_{self._offset}_{self._name.lower().replace(' ', '_')}"
        )

    @property
    def native_value(self) -> int | float | str | None:
        """Return the current sensor value."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        async with self._device.lock:
            payload = await self.hass.async_add_executor_job(
                self._device.read_block_cached, self._block
            )
            await asyncio.sleep(0.01)  # Brief pause for device readiness

        raw_bytes = payload[self._offset : self._offset + self._length]
        self._state = decode_value(raw_bytes, self._decode_type, self._factor)