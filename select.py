"""Select entity for THZ integration.

This module provides dropdown/select entities for the THZ heat pump,
allowing selection of operation modes and other enumerated settings.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice


_LOGGER = logging.getLogger(__name__)

# Value mappings for select entities
# Maps numeric values to human-readable option strings
SELECT_MAP: dict[str, dict[str, str]] = {
    "2opmode": {
        "1": "standby",
        "11": "automatic",
        "3": "DAYmode",
        "4": "setback",
        "5": "DHWmode",
        "14": "manual",
        "0": "emergency",
    },
    "OpModeHC": {
        "1": "normal",
        "2": "setback",
        "3": "standby",
        "4": "restart",
        "5": "restart",
    },
    "OpMode2": {
        "0": "manual",
        "1": "automatic",
    },
    "SomWinMode": {
        "01": "winter",
        "02": "summer",
    },
    "weekday": {
        "0": "Monday",
        "1": "Tuesday",
        "2": "Wednesday",
        "3": "Thursday",
        "4": "Friday",
        "5": "Saturday",
        "6": "Sunday",
    },
    "faultmap": {
        "0": "n.a.",
        "1": "F01_AnodeFault",
        "2": "F02_SafetyTempDelimiterEngaged",
        "3": "F03_HighPreasureGuardFault",
        "4": "F04_LowPreasureGuardFault",
        "5": "F05_OutletFanFault",
        "6": "F06_InletFanFault",
        "7": "F07_MainOutputFanFault",
        "11": "F11_LowPreasureSensorFault",
        "12": "F12_HighPreasureSensorFault",
        "15": "F15_DHW_TemperatureFault",
        "17": "F17_DefrostingDurationExceeded",
        "20": "F20_SolarSensorFault",
        "21": "F21_OutsideTemperatureSensorFault",
        "22": "F22_HotGasTemperatureFault",
        "23": "F23_CondenserTemperatureSensorFault",
        "24": "F24_EvaporatorTemperatureSensorFault",
        "26": "F26_ReturnTemperatureSensorFault",
        "28": "F28_FlowTemperatureSensorFault",
        "29": "F29_DHW_TemperatureSensorFault",
        "30": "F30_SoftwareVersionFault",
        "31": "F31_RAMfault",
        "32": "F32_EEPromFault",
        "33": "F33_ExtractAirHumiditySensor",
        "34": "F34_FlowSensor",
        "35": "F35_minFlowCooling",
        "36": "F36_MinFlowRate",
        "37": "F37_MinWaterPressure",
        "40": "F40_FloatSwitch",
        "50": "F50_SensorHeatPumpReturn",
        "51": "F51_SensorHeatPumpFlow",
        "52": "F52_SensorCondenserOutlet",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ Select entities from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: The config entry for this integration.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    entities: list[THZSelect] = []
    write_manager: RegisterMapManagerWrite = hass.data[DOMAIN]["write_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]
    write_registers = write_manager.get_all_registers()

    _LOGGER.debug("write_registers: %s", write_registers)

    for name, entry in write_registers.items():
        if entry["type"] == "select":
            _LOGGER.debug(
                "Creating Select for %s with command %s", name, entry["command"]
            )
            entity = THZSelect(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                decode_type=entry.get("decode_type"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)

    async_add_entities(entities)


class THZSelect(SelectEntity):
    """Representation of a THZ Select entity.

    This entity provides dropdown selection for operation modes
    and other enumerated settings of the THZ heat pump.

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
        decode_type: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the THZ Select entity.

        Args:
            name: Entity name.
            command: Command hex string for device communication.
            device: The THZ device instance.
            icon: Optional icon override.
            decode_type: The decode type key for SELECT_MAP lookup.
            unique_id: Optional unique ID override.
        """
        self._attr_name = name
        self._command = command
        self._device = device
        self._attr_icon = icon or "mdi:format-list-bulleted"
        self._attr_unique_id = (
            unique_id or f"thz_select_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._decode_type = decode_type

        # Set options from SELECT_MAP if decode_type is defined
        if decode_type and decode_type in SELECT_MAP:
            self._attr_options = list(SELECT_MAP[decode_type].values())
            _LOGGER.debug("Options for %s (%s): %s", name, decode_type, self._attr_options)
        else:
            self._attr_options = []

        self._attr_current_option: str | None = None

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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._attr_current_option

    async def async_update(self) -> None:
        """Fetch new state data for the select entity."""
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                4,
                2,
            )
            _LOGGER.debug(
                "Read bytes for %s (%s): %s",
                self._attr_name,
                self._command,
                value_bytes.hex() if value_bytes else "None",
            )

        value = int.from_bytes(value_bytes, byteorder="little", signed=False)
        _LOGGER.debug("Value for %s (%s): %s", self._attr_name, self._command, value)

        # Map numeric value to option string
        if self._decode_type and self._decode_type in SELECT_MAP:
            # SomWinMode uses zero-padded values
            value_str = (
                str(value).zfill(2)
                if self._decode_type == "SomWinMode"
                else str(value)
            )
            _LOGGER.debug(
                "Mapping value %s to option for %s (%s)",
                value_str,
                self._attr_name,
                self._command,
            )
            self._attr_current_option = SELECT_MAP[self._decode_type].get(value_str)
            _LOGGER.debug(
                "Current option for %s (%s): %s",
                self._attr_name,
                self._command,
                self._attr_current_option,
            )
        else:
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Set the selected option.

        Args:
            option: The option string to select.
        """
        if not self._decode_type or self._decode_type not in SELECT_MAP:
            _LOGGER.warning("No decode type defined for %s", self._attr_name)
            return

        # Create reverse mapping from option string to numeric value
        reverse_map = {v: int(k) for k, v in SELECT_MAP[self._decode_type].items()}

        if option not in reverse_map:
            _LOGGER.warning("Unknown option %s for %s", option, self._attr_name)
            return

        value_int = reverse_map[option]
        _LOGGER.debug("Setting %s to %s (value: %s)", self._attr_name, option, value_int)

        value_bytes = value_int.to_bytes(2, byteorder="little", signed=False)
        _LOGGER.debug("Value bytes to write: %s", value_bytes.hex())

        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_bytes,
            )
            await asyncio.sleep(0.01)

        _LOGGER.debug("Set %s to %s (value: %s)", self._attr_name, option, value_int)
        self._attr_current_option = option