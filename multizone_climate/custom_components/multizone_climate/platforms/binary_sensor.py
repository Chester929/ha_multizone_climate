"""Binary sensor platform for Multizone Climate integration."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    - Redis connection status
    - Minimum valves requirement status
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    redis_client = data["redis_client"]

    entities = [
        MultizoneEnabledSensor(coordinator, config_entry),
        RedisConnectionSensor(redis_client, config_entry),
        MinimumValvesSensor(coordinator, config_entry),
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


class RedisConnectionSensor(BinarySensorEntity):
    """Binary sensor showing Redis connection status."""

    def __init__(self, redis_client: Any, config_entry: ConfigEntry) -> None:
        """
        Initialize Redis connection sensor.

        Args:
            redis_client: Redis client instance
            config_entry: Config entry for device info
        """
        self.redis_client = redis_client
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_redis_connection"
        self._attr_name = "Redis Connection"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_should_poll = True  # Poll to check connection status

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
            bool: True if Redis is connected
        """
        # Check if Redis client is connected using public property
        return self.redis_client.is_connected if self.redis_client else False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True  # Always available to show connection status


class MinimumValvesSensor(BinarySensorEntity):
    """Binary sensor showing minimum valves requirement status."""

    def __init__(self, coordinator: Any, config_entry: ConfigEntry) -> None:
        """
        Initialize minimum valves sensor.

        Args:
            coordinator: Data update coordinator
            config_entry: Config entry for device info
        """
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_minimum_valves_ok"
        self._attr_name = "Minimum Valves Requirement"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
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
            bool: True if minimum valves requirement is satisfied
        """
        # Get zone data from coordinator
        data = self.coordinator.data
        if not data:
            return False

        zones = data.get("zones", {})
        if not zones:
            return False

        # Count open valves
        open_valves = sum(
            1 for zone in zones.values()
            if zone.get("valve_state") == "open"
        )

        # Get minimum requirement from config
        config = self.coordinator.get_config()
        if not config:
            return True  # Default to OK if no config

        min_valves_required = config.get("min_valves_open", 1)

        # Return True if requirement is met
        return open_valves >= min_valves_required

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
