"""Config flow for THZ integration.

This module handles the configuration flow for setting up the THZ heat pump
integration, supporting both USB/serial and network (ser2net) connections.
"""
from __future__ import annotations

import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry

from .const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_IP,
    CONNECTION_USB,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOG_LEVELS,
)
from .thz_device import THZDevice


_LOGGER = logging.getLogger(__name__)


class THZConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Stiebel Eltron THZ (LAN or USB).

    This flow guides the user through:
    1. Selecting connection type (USB or Network)
    2. Configuring connection parameters
    3. Setting device name and area
    4. Configuring log level
    5. Detecting firmware and available blocks
    6. Setting refresh intervals per block
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.connection_data: dict[str, Any] = {}
        self.blocks: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step: connection type selection.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or redirect to connection-specific step.
        """
        if user_input is not None:
            if user_input["connection_type"] == CONNECTION_IP:
                return await self.async_step_ip()
            return await self.async_step_usb()

        schema = vol.Schema(
            {
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_IP): vol.In(
                    {
                        CONNECTION_IP: "Network (ser2net)",
                        CONNECTION_USB: "USB / Serial",
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device name and area configuration.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or redirect to log configuration step.
        """
        if user_input is not None:
            self.connection_data["alias"] = user_input.get("alias", "").strip()
            self.connection_data["area"] = user_input.get("area", "").strip()
            return await self.async_step_log()

        # Get available areas
        ar = area_registry.async_get(self.hass)
        areas = {area.id: area.name for area in ar.async_list_areas()}
        areas[""] = "-- No Area --"

        schema = vol.Schema(
            {
                vol.Optional(
                    "alias", default=self.connection_data.get("alias", "")
                ): str,
                vol.Optional(
                    "area", default=self.connection_data.get("area", "")
                ): str,
            }
        )
        return self.async_show_form(step_id="name", data_schema=schema)

    async def async_step_ip(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle network connection configuration.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or redirect to name step.
        """
        if user_input is not None:
            self.connection_data = user_input
            return await self.async_step_name()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_IP): vol.In(
                    [CONNECTION_IP]
                ),
            }
        )
        return self.async_show_form(step_id="ip", data_schema=schema)

    async def async_step_usb(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle USB/serial connection configuration.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or redirect to name step.
        """
        if user_input is not None:
            self.connection_data = user_input
            return await self.async_step_name()

        ports = await self._get_serial_ports()

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=ports[0]): vol.In(ports),
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_USB): vol.In(
                    [CONNECTION_USB]
                ),
                vol.Required("Baudrate", default=DEFAULT_BAUDRATE): int,
            }
        )
        return self.async_show_form(step_id="usb", data_schema=schema)

    async def async_step_log(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle log level configuration.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or redirect to block detection step.
        """
        if user_input is not None:
            self.connection_data["log_level"] = LOG_LEVELS[user_input["log_level"]]
            return await self.async_step_detect_blocks()

        schema = vol.Schema(
            {
                vol.Required("log_level", default="Info"): vol.In(
                    list(LOG_LEVELS.keys())
                ),
            }
        )
        return self.async_show_form(step_id="log", data_schema=schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration initiated from the device UI.

        Args:
            user_input: User form input, if any.

        Returns:
            Form result or abort with reconfigured reason.
        """
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id)

        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            level_name = user_input.get("log_level", "info").upper()
            level = getattr(logging, level_name, logging.INFO)
            logging.getLogger("custom_components.thz").setLevel(level)

            # Update config entry with new values
            self.hass.config_entries.async_update_entry(entry, data=user_input)

            # Reload integration to apply changes
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigured")

        # Prefill current values
        data = entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=await self._build_reconfigure_schema(data),
        )

    async def _build_reconfigure_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        """Build the reconfiguration form schema with defaults.

        Args:
            defaults: Current configuration values to use as defaults.

        Returns:
            Voluptuous schema for the reconfigure form.
        """
        defaults = defaults or {}

        ports = await self._get_serial_ports()
        ar = area_registry.async_get(self.hass)
        areas = {area.id: area.name for area in ar.async_list_areas()}
        areas[""] = "-- No Area --"

        return vol.Schema(
            {
                vol.Required(
                    "port",
                    default=defaults.get("port", ports[0]),
                ): str,
                vol.Required(
                    "baudrate",
                    default=defaults.get("baudrate", DEFAULT_BAUDRATE),
                ): int,
                vol.Required(
                    "update_interval",
                    default=defaults.get("update_interval", DEFAULT_UPDATE_INTERVAL),
                ): int,
                vol.Optional(
                    "alias",
                    default=defaults.get("alias", ""),
                ): str,
                vol.Optional(
                    "area",
                    default=defaults.get("area", ""),
                ): vol.In(areas),
                vol.Required(
                    "log_level",
                    default=defaults.get("log_level", "info"),
                ): vol.In(["debug", "info", "warning", "error"]),
            }
        )

    async def _get_serial_ports(self) -> list[str]:
        """Get available serial ports.

        Returns:
            List of available serial port device paths, or default paths if none found.
        """
        ports = await self.hass.async_add_executor_job(
            serial.tools.list_ports.comports
        )
        if ports:
            return [p.device for p in ports]
        # Fallback to common default paths
        return ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyAMA0"]

    async def async_step_detect_blocks(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Detect firmware version and available register blocks.

        This step connects to the heat pump to read firmware version
        and determine which data blocks are available.

        Args:
            user_input: Not used in this step.

        Returns:
            Redirect to refresh intervals step or abort on error.
        """
        data = self.connection_data
        conn_type = data["connection_type"]

        try:

            def create_and_init_device() -> THZDevice:
                if conn_type == CONNECTION_USB:
                    return THZDevice(
                        connection="usb",
                        port=data.get(CONF_DEVICE),
                        baudrate=DEFAULT_BAUDRATE,
                    )
                return THZDevice(
                    connection="ip",
                    host=data.get(CONF_HOST),
                    port=data.get(CONF_PORT, DEFAULT_PORT),
                    baudrate=data.get("baudrate", DEFAULT_BAUDRATE),
                )

            device: THZDevice = await self.hass.async_add_executor_job(
                create_and_init_device
            )

            await device.async_initialize(self.hass)

            firmware = device.firmware_version
            _LOGGER.info("Firmware detected: %s", firmware)

            blocks = device.available_reading_blocks
            _LOGGER.info("Available blocks: %s", blocks)

        except Exception:
            _LOGGER.exception("Error reading firmware/blocks")
            return self.async_abort(reason="cannot_detect_blocks")

        self.blocks = blocks
        self.connection_data["firmware"] = firmware
        return await self.async_step_refresh_blocks()

    async def async_step_refresh_blocks(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure refresh intervals per register block.

        Args:
            user_input: User form input containing refresh intervals.

        Returns:
            Form result or create config entry on completion.
        """
        blocks = self.blocks

        if user_input is not None:
            refresh_intervals = {b: user_input[f"refresh_{b}"] for b in blocks}
            data = {**self.connection_data, "refresh_intervals": refresh_intervals}
            title = (
                f"THZ ({data['connection_type']}: "
                f"{data.get('host') or data.get('device')})"
            )
            return self.async_create_entry(title=title, data=data)

        schema_dict: dict[vol.Marker, Any] = {}
        for block in blocks:
            schema_dict[vol.Optional(f"refresh_{block}", default=600)] = vol.All(
                int, vol.Range(min=5, max=86400)
            )

        schema = vol.Schema(schema_dict)
        return self.async_show_form(
            step_id="refresh_blocks",
            data_schema=schema,
            description_placeholders={
                "hint": "Refresh interval per block (seconds)"
            },
        )