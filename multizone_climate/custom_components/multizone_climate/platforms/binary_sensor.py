"""Binary sensor platform for Multizone Climate integration."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up binary sensor entities.

    Creates binary sensors for:
    - Multizone enabled status
    - System status monitoring
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        MultizoneEnabledSensor(coordinator, config_entry),
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d binary sensor entities", len(entities))


class MultizoneEnabledSensor(BinarySensorEntity):
    """Binary sensor showing multizone enabled status."""

    def __init__(self, coordinator: Any, config_entry: ConfigEntry) -> None:
        """
        Initialize multizone enabled sensor.

        Args:
            coordinator: Data update coordinator
            config_entry: Config entry for device info
        """
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_multizone_enabled_status"
        self._attr_name = "Multizone Enabled Status"
        self._attr_should_poll = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, "main")},
            "name": "Multizone Climate",
            "manufacturer": "Multizone Climate",
            "model": "Main Controller",
        }

    @property
    def is_on(self) -> bool:
        """
        Return binary sensor state.

        Returns:
            bool: True if multizone is enabled
        """
        data = self.coordinator.get_main_climate_data()
        if data:
            return bool(data.get("multizone_enabled", False))
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
