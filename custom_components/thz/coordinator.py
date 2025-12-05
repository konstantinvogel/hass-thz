"""DataUpdateCoordinator for THZ integration.

This module provides the coordinator that manages data fetching from the
THZ heat pump device.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

if TYPE_CHECKING:
    from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


class THZDataUpdateCoordinator(DataUpdateCoordinator[bytes]):
    """Coordinator for fetching THZ block data.

    Each block has its own coordinator instance with a configurable
    update interval.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device: THZDevice,
        block_name: str,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            device: The THZ device instance.
            block_name: The name of the block to fetch (e.g., "p01").
            update_interval: Update interval in seconds.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"THZ {block_name}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.device = device
        self.block_name = block_name

    async def _async_update_data(self) -> bytes:
        """Fetch data from the THZ device.

        Returns:
            The raw bytes read from the device block.

        Raises:
            UpdateFailed: If reading the block fails.
        """
        block_bytes = bytes.fromhex(self.block_name.strip("pxx"))
        try:
            _LOGGER.debug("Reading block %s...", self.block_name)
            return await self.hass.async_add_executor_job(
                self.device.read_block, block_bytes, "get"
            )
        except Exception as err:
            raise UpdateFailed(
                f"Error reading block {self.block_name}: {err}"
            ) from err
