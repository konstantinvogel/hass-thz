"""Binary sensor platform for THZ Heat Pump."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class THZBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a THZ binary sensor entity."""
    
    pass


# Define all binary sensors
BINARY_SENSORS: tuple[THZBinarySensorEntityDescription, ...] = (
    # Compressor and heating stages
    THZBinarySensorEntityDescription(
        key="compressor",
        translation_key="compressor",
        name="Compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heat-pump",
    ),
    THZBinarySensorEntityDescription(
        key="boosterStage1",
        translation_key="booster_stage1",
        name="Booster Stage 1",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    THZBinarySensorEntityDescription(
        key="boosterStage2",
        translation_key="booster_stage2",
        name="Booster Stage 2",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    THZBinarySensorEntityDescription(
        key="boosterStage3",
        translation_key="booster_stage3",
        name="Booster Stage 3",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    
    # Pumps
    THZBinarySensorEntityDescription(
        key="heatingCircuitPump",
        translation_key="heating_circuit_pump",
        name="Heating Circuit Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    THZBinarySensorEntityDescription(
        key="dhwPump",
        translation_key="dhw_pump",
        name="DHW Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    THZBinarySensorEntityDescription(
        key="solarPump",
        translation_key="solar_pump",
        name="Solar Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    
    # Valves
    THZBinarySensorEntityDescription(
        key="mixerOpen",
        translation_key="mixer_open",
        name="Mixer Open",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-open",
    ),
    THZBinarySensorEntityDescription(
        key="mixerClosed",
        translation_key="mixer_closed",
        name="Mixer Closed",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-closed",
    ),
    THZBinarySensorEntityDescription(
        key="heatPipeValve",
        translation_key="heat_pipe_valve",
        name="Heat Pipe Valve",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve",
    ),
    THZBinarySensorEntityDescription(
        key="diverterValve",
        translation_key="diverter_valve",
        name="Diverter Valve",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve",
    ),
    
    # Pressure sensors (these are "OK" indicators)
    THZBinarySensorEntityDescription(
        key="highPressureSensor",
        translation_key="high_pressure_sensor",
        name="High Pressure OK",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:gauge-full",
    ),
    THZBinarySensorEntityDescription(
        key="lowPressureSensor",
        translation_key="low_pressure_sensor",
        name="Low Pressure OK",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:gauge-empty",
    ),
    
    # Other sensors
    THZBinarySensorEntityDescription(
        key="evuRelease",
        translation_key="evu_release",
        name="EVU Release",
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:transmission-tower",
    ),
    THZBinarySensorEntityDescription(
        key="evaporatorIceMonitor",
        translation_key="evaporator_ice_monitor",
        name="Evaporator Ice Monitor",
        device_class=BinarySensorDeviceClass.COLD,
        icon="mdi:snowflake-alert",
    ),
    THZBinarySensorEntityDescription(
        key="signalAnode",
        translation_key="signal_anode",
        name="Anode Signal",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle",
    ),
    THZBinarySensorEntityDescription(
        key="STB",
        translation_key="stb",
        name="Safety Temperature Limiter",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:alert",
    ),
    THZBinarySensorEntityDescription(
        key="ovenFireplace",
        translation_key="oven_fireplace",
        name="Oven/Fireplace Active",
        device_class=BinarySensorDeviceClass.HEAT,
        icon="mdi:fireplace",
    ),
    THZBinarySensorEntityDescription(
        key="pasteurisationMode",
        translation_key="pasteurisation_mode",
        name="Pasteurisation Mode",
        device_class=BinarySensorDeviceClass.HEAT,
        icon="mdi:bacteria",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ binary sensors based on a config entry."""
    coordinator: THZDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[THZBinarySensor] = []
    
    for description in BINARY_SENSORS:
        # Only add sensor if data is available
        if coordinator.data and description.key in coordinator.data:
            entities.append(THZBinarySensor(coordinator, description))
        else:
            _LOGGER.debug(
                "Skipping binary sensor %s - not available in data", 
                description.key
            )

    async_add_entities(entities)


class THZBinarySensor(
    CoordinatorEntity[THZDataUpdateCoordinator], 
    BinarySensorEntity
):
    """Representation of a THZ binary sensor."""

    entity_description: THZBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: THZDataUpdateCoordinator,
        description: THZBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
            
        value = self.coordinator.data.get(self.entity_description.key)
        
        if value is None:
            return None
            
        # Handle different value types
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ("1", "true", "on", "yes")
            
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available 
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )
