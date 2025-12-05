"""Base entity for THZ integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import THZDataUpdateCoordinator

if TYPE_CHECKING:
    from .thz_device import THZDevice


class THZBaseEntity(CoordinatorEntity[THZDataUpdateCoordinator]):
    """Base class for THZ entities with common functionality."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: THZDataUpdateCoordinator,
        device: THZDevice,
        name: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the THZ base entity.

        Args:
            coordinator: The data update coordinator.
            device: The THZ device instance.
            name: The entity name.
            unique_id_suffix: Suffix for the unique ID.
        """
        super().__init__(coordinator)
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{unique_id_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id or "thz_device")},
            name="THZ Wärmepumpe",
            manufacturer="Stiebel Eltron / Tecalor",
            model="THZ",
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self._device is not None
