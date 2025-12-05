"""DataUpdateCoordinator for THZ Heat Pump."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
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
from .thz_protocol import THZProtocol, THZProtocolError

_LOGGER = logging.getLogger(__name__)


class THZDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates from the heat pump."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self._protocol: THZProtocol | None = None
        
        # Get configuration
        self._port = entry.data[CONF_SERIAL_PORT]
        self._baudrate = entry.data.get(CONF_BAUDRATE, 115200)
        
        # Firmware info (will be populated on first update)
        self.firmware_version: str | None = None
        self.firmware_date: str | None = None
        
        # Backup tracking
        self._backup_created = False
        self._backup_path: str | None = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def protocol(self) -> THZProtocol:
        """Get or create the protocol instance."""
        if self._protocol is None:
            self._protocol = THZProtocol(
                self._port,
                self._baudrate,
                firmware="auto"
            )
        return self._protocol

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the heat pump."""
        try:
            # Run the blocking I/O in executor
            data = await self.hass.async_add_executor_job(
                self._fetch_data
            )
            return data
        except THZProtocolError as err:
            raise UpdateFailed(f"Error communicating with heat pump: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _fetch_data(self) -> dict[str, Any]:
        """Fetch data from the heat pump (blocking)."""
        protocol = self.protocol
        protocol.open()
        
        try:
            # Detect firmware on first run
            if self.firmware_version is None:
                try:
                    fw_info = protocol.get_firmware_info()
                    if "version" in fw_info:
                        version = fw_info["version"]
                        major = int(version) // 100 if isinstance(version, (int, float)) else 0
                        minor = int(version) % 100 if isinstance(version, (int, float)) else 0
                        self.firmware_version = f"{major}.{minor:02d}"
                        _LOGGER.info("Heat pump firmware: %s", self.firmware_version)
                        
                        # Build date string
                        if all(k in fw_info for k in ["date_day", "date_month", "date_year"]):
                            self.firmware_date = (
                                f"{int(fw_info['date_day']):02d}."
                                f"{int(fw_info['date_month']):02d}."
                                f"{int(fw_info['date_year'])}"
                            )
                except THZProtocolError as err:
                    _LOGGER.warning("Failed to read firmware info: %s", err)
                    self.firmware_version = "unknown"
            
            # Read all sensor data
            data = protocol.get_all_sensor_data()
            
            # Create backup on first successful read
            if not self._backup_created and data:
                self._create_register_backup(protocol, data)
            
            # Add metadata
            data["_firmware"] = self.firmware_version
            data["_firmware_date"] = self.firmware_date
            
            _LOGGER.debug("Fetched data: %s", data)
            return data
            
        except Exception:
            # On error, close connection so it gets reopened on next try
            protocol.close()
            raise

    def _create_register_backup(self, protocol: THZProtocol, parsed_data: dict[str, Any]) -> None:
        """Create a backup of all register raw data on first read.
        
        This backup can be used to restore settings if something goes wrong.
        The backup is stored in the Home Assistant config directory.
        """
        try:
            # Get raw register data
            raw_registers = protocol.get_all_raw_registers()
            
            # Build backup data structure
            backup_data = {
                "created_at": datetime.now().isoformat(),
                "firmware_version": self.firmware_version,
                "firmware_date": self.firmware_date,
                "serial_port": self._port,
                "baudrate": self._baudrate,
                "raw_registers": raw_registers,
                "parsed_data": {k: v for k, v in parsed_data.items() if not k.startswith("_")},
            }
            
            # Create backup directory
            backup_dir = self.hass.config.path("backups", "hass_thz")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_port = self._port.replace("/", "_").replace("\\", "_").replace(":", "")
            backup_filename = f"thz_backup_{safe_port}_{timestamp}.json"
            self._backup_path = os.path.join(backup_dir, backup_filename)
            
            # Write backup file
            with open(self._backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)
            
            self._backup_created = True
            _LOGGER.info(
                "Created register backup at: %s (Firmware: %s)", 
                self._backup_path, 
                self.firmware_version
            )
            
        except Exception as err:
            _LOGGER.warning("Failed to create register backup: %s", err)
            # Don't fail the integration if backup fails
            self._backup_created = True  # Don't retry

    async def async_close(self) -> None:
        """Close the connection."""
        if self._protocol:
            await self.hass.async_add_executor_job(self._protocol.close)
            self._protocol = None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for the heat pump."""
        return {
            "identifiers": {(DOMAIN, self._port)},
            "name": "THZ Heat Pump",
            "manufacturer": "Tecalor / Stiebel Eltron",
            "model": "THZ / LWZ",
            "sw_version": self.firmware_version,
        }
