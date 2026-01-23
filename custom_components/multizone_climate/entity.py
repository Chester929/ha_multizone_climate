"""Entity base class for Multizone Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class MultizoneClimateEntity(Entity):
    """Base entity for Multizone Climate integration."""

    def __init__(self, coordinator: Any, unique_id_suffix: str) -> None:
        """
        Initialize base entity.

        Args:
            coordinator: Data update coordinator
            unique_id_suffix: Suffix for unique ID
        """
        self.coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{unique_id_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """
        Return device information.

        Returns:
            DeviceInfo: Device information for grouping entities
        """
        # TODO: Return device info for entity grouping
        return DeviceInfo(
            identifiers={(DOMAIN, "multizone_climate_main")},
            name="Multizone Climate",
            manufacturer="Chester929",
            model="Multizone Climate Controller",
        )

    @property
    def should_poll(self) -> bool:
        """
        Return False as updates are coordinated.

        Returns:
            bool: False (coordinator-based updates)
        """
        return False

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Cleanup handled by async_on_remove in async_added_to_hass
        pass
