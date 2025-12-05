"""THZ Integration for Home Assistant.

This integration provides control for Stiebel Eltron LWZ / Tecalor THZ heat pumps.
Based on the FHEM THZ module by immi.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .coordinator import THZDataUpdateCoordinator
from .thz_device import THZDevice

if TYPE_CHECKING:
    from .register_maps.register_map_manager import (
        RegisterMapManager,
        RegisterMapManagerWrite,
    )

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up THZ from a config entry.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry to set up.

    Returns:
        True if setup was successful.

    Raises:
        ValueError: If an invalid connection type is specified.
    """
    # Configure logging level
    log_level_str = config_entry.data.get("log_level", "info")
    _LOGGER.setLevel(getattr(logging, log_level_str.upper(), logging.INFO))
    _LOGGER.info("Log level set to: %s", log_level_str)
    _LOGGER.debug("THZ async_setup_entry called with entry: %s", config_entry.as_dict())

    hass.data.setdefault(DOMAIN, {})

    data = config_entry.data
    conn_type = data["connection_type"]

    # Initialize device based on connection type
    if conn_type == "ip":
        device = THZDevice(connection="ip", host=data["host"], tcp_port=data["port"])
    elif conn_type == "usb":
        device = THZDevice(connection="usb", port=data["device"])
    else:
        raise ValueError(f"Invalid connection type: {conn_type}")

    await device.async_initialize(hass)
    _LOGGER.info("THZ device initialized (FW %s)", device.firmware_version)

    # Register device in Home Assistant device registry
    dev_reg = dr.async_get(hass)
    unique_id = device.unique_id or f"thz_{conn_type}"
    device_name = data.get("alias") or f"THZ {data.get('host') or data.get('device')}"

    device_entry = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        name=device_name,
        manufacturer="Stiebel Eltron / Tecalor",
        model="THZ",
        sw_version=device.firmware_version,
        suggested_area=data.get("area"),
    )
    _LOGGER.debug("Device registry entry created/updated: %s", device_entry.id)

    # Store managers and device in hass.data
    hass.data[DOMAIN]["write_manager"] = device.write_register_map_manager
    hass.data[DOMAIN]["register_manager"] = device.register_map_manager
    hass.data[DOMAIN]["device"] = device

    # Create coordinators for each block with its own refresh interval
    coordinators: dict[str, THZDataUpdateCoordinator] = {}
    refresh_intervals = config_entry.data.get("refresh_intervals", {})

    for block, interval in refresh_intervals.items():
        coordinator = THZDataUpdateCoordinator(
            hass=hass,
            device=device,
            block_name=block,
            update_interval=int(interval),
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[block] = coordinator

    # Store in hass.data for access by platforms
    hass.data[DOMAIN][config_entry.entry_id] = {
        "device": device,
        "coordinators": coordinators,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to unload.

    Returns:
        True if unload was successful.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
