"""Binary sensor platform for THZ Heat Pump."""
from __future__ import annotations

import logging
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


# =============================================================================
# Binary sensors from sGlobal (FB) - Status values
# =============================================================================
BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    # Compressor and booster stages
    BinarySensorEntityDescription(
        key="compressor",
        name="Compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heat-pump",
    ),
    BinarySensorEntityDescription(
        key="boosterStage1",
        name="Booster Stage 1",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    BinarySensorEntityDescription(
        key="boosterStage2",
        name="Booster Stage 2",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    BinarySensorEntityDescription(
        key="boosterStage3",
        name="Booster Stage 3",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heating-coil",
    ),
    # Pumps
    BinarySensorEntityDescription(
        key="dhwPump",
        name="DHW Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    BinarySensorEntityDescription(
        key="heatingCircuitPump",
        name="Heating Circuit Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:pump",
    ),
    # Valves
    BinarySensorEntityDescription(
        key="mixerOpen",
        name="Mixer Open",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-open",
    ),
    BinarySensorEntityDescription(
        key="mixerClosed",
        name="Mixer Closed",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-closed",
    ),
    BinarySensorEntityDescription(
        key="heatPipeValve",
        name="Heat Pipe Valve",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve",
    ),
    BinarySensorEntityDescription(
        key="diverterValve",
        name="Diverter Valve",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve",
    ),
    # Inside temp sensor validity
    BinarySensorEntityDescription(
        key="insideTempValid",
        name="Inside Temp Sensor Valid",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:thermometer-check",
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
            _LOGGER.debug("Adding binary sensor: %s", description.key)
        else:
            _LOGGER.debug(
                "Skipping binary sensor %s - not available in data",
                description.key
            )

    async_add_entities(entities)
    _LOGGER.info("Added %d binary sensors", len(entities))


class THZBinarySensor(
    CoordinatorEntity[THZDataUpdateCoordinator],
    BinarySensorEntity
):
    """Representation of a THZ binary sensor."""

    entity_description: BinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: THZDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
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
