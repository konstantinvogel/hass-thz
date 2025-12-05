"""Config flow for THZ Heat Pump integration."""
from __future__ import annotations

import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import (
    CONF_BAUDRATE,
    CONF_SERIAL_PORT,
    DEFAULT_BAUDRATE,
    DOMAIN,
)
from .thz_protocol import THZProtocol

_LOGGER = logging.getLogger(__name__)


def get_serial_ports() -> list[str]:
    """Get available serial ports."""
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append(port.device)
    return ports


class THZConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for THZ Heat Pump."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Get available serial ports
        ports = await self.hass.async_add_executor_job(get_serial_ports)
        
        if not ports:
            ports = ["/dev/ttyUSB0", "/dev/ttyACM0", "COM1", "COM2", "COM3"]

        if user_input is not None:
            serial_port = user_input[CONF_SERIAL_PORT]
            baudrate = user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)

            # Try to connect, validate, and detect firmware
            detected_firmware = None
            try:
                protocol = THZProtocol(serial_port, baudrate)
                
                # Test connection and detect firmware automatically
                def test_and_detect():
                    protocol.open()
                    fw = protocol.detect_firmware()
                    protocol.close()
                    return fw
                
                detected_firmware = await self.hass.async_add_executor_job(
                    test_and_detect
                )
                _LOGGER.info("Detected firmware: %s", detected_firmware)
                
            except Exception as err:
                _LOGGER.error("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"

            if not errors and detected_firmware:
                # Set unique ID based on serial port
                await self.async_set_unique_id(serial_port)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, f"THZ Heat Pump ({serial_port})"),
                    data={
                        CONF_SERIAL_PORT: serial_port,
                        CONF_BAUDRATE: baudrate,
                    },
                )

        # Build schema with detected ports - firmware is auto-detected
        data_schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT): vol.In(ports) if ports else str,
                vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In(
                    [9600, 19200, 38400, 57600, 115200]
                ),
                vol.Optional(CONF_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
