"""Binary sensor platform for THZ Heat Pump.

Note: Currently no binary sensor data is being parsed from the heat pump.
This file is a placeholder for future implementation when status registers
are properly implemented.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ binary sensors based on a config entry."""
    coordinator: THZDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # No binary sensors implemented yet - status registers need parsing
    _LOGGER.debug("No binary sensors available yet")
    async_add_entities([])
