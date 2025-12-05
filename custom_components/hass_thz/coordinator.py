"""DataUpdateCoordinator for THZ Heat Pump."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BAUDRATE,
    CONF_SERIAL_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .thz_protocol import (
    THZConnection,
    REGISTERS,
    PARSERS,
    parse_firmware,
)

_LOGGER = logging.getLogger(__name__)


class THZDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates from the heat pump."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self._connection: THZConnection | None = None
        
        # Get configuration
        self._port = entry.data[CONF_SERIAL_PORT]
        self._baudrate = entry.data.get(CONF_BAUDRATE, 115200)
        
        # Firmware info (will be populated on first update)
        self.firmware_version: str | None = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def connection(self) -> THZConnection:
        """Get or create the connection instance."""
        if self._connection is None:
            self._connection = THZConnection(self._port, self._baudrate)
        return self._connection

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the heat pump."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
            return data
        except Exception as err:
            _LOGGER.exception("Error fetching data from heat pump")
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err

    def _fetch_data(self) -> dict[str, Any]:
        """Fetch data from the heat pump (blocking)."""
        conn = self.connection
        
        if not conn.is_connected():
            conn.connect()
        
        data: dict[str, Any] = {}
        
        try:
            # Read firmware on first run
            if self.firmware_version is None:
                response = conn.read_register("FD")
                if response.success and response.data:
                    fw_data = parse_firmware(response.data)
                    self.firmware_version = fw_data.get("version", "unknown")
                    _LOGGER.info("Heat pump firmware: %s", self.firmware_version)
                else:
                    self.firmware_version = "unknown"
            
            # Read main registers
            registers_to_read = ["FB", "F4", "09", "D1"]  # sGlobal, sHC1, sHistory, sLast
            
            for reg in registers_to_read:
                if reg not in REGISTERS:
                    continue
                    
                response = conn.read_register(reg)
                
                if response.success and response.data:
                    # Get parser for this register
                    parser_name = REGISTERS[reg].get("parse", "raw")
                    if parser_name in PARSERS:
                        parsed = PARSERS[parser_name](response.data)
                        # Flatten parsed data into main dict
                        for key, value in parsed.items():
                            if not key.startswith("parse_"):
                                data[key] = value
                    else:
                        data[f"{reg}_raw"] = response.data
                else:
                    _LOGGER.debug(
                        "Failed to read register %s: %s", 
                        reg, 
                        response.error_message
                    )
            
            # Add metadata
            data["_firmware"] = self.firmware_version
            
            _LOGGER.debug("Fetched data keys: %s", list(data.keys()))
            return data
            
        except Exception:
            # On error, disconnect so it gets reconnected on next try
            conn.disconnect()
            raise

    async def async_close(self) -> None:
        """Close the connection."""
        if self._connection:
            await self.hass.async_add_executor_job(self._connection.disconnect)
            self._connection = None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for the heat pump."""
        return {
            "identifiers": {(DOMAIN, self._port)},
            "name": "Tecalor THZ / Stiebel Eltron LWZ",
            "manufacturer": "Tecalor / Stiebel Eltron",
            "model": "THZ / LWZ Heat Pump",
            "sw_version": self.firmware_version,
        }
