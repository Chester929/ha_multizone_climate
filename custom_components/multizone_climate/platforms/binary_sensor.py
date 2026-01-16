"""Binary sensor platform for Multizone Climate integration."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up binary sensor entities.

    Creates binary sensors for:
    - System status (OK/Error)
    - Redis connection status
    - Minimum valves requirement status
    """
    # For now, binary sensors are optional
    # Can be implemented later if needed for status monitoring
    _LOGGER.debug("Binary sensor platform setup (no entities yet)")


class MultizoneBinarySensor(BinarySensorEntity):
    """Base binary sensor for multizone climate."""

    def __init__(self, coordinator: Any, sensor_type: str) -> None:
        """
        Initialize binary sensor.

        Args:
            coordinator: Data update coordinator
            sensor_type: Type of binary sensor
        """
        self.coordinator = coordinator
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return sensor name."""
        return f"Multizone {self.sensor_type}"

    @property
    def is_on(self) -> bool:
        """
        Return binary sensor state.

        Returns:
            bool: True if condition is met
        """
        # Get state from coordinator data
        if not hasattr(self.coordinator, "data") or self.coordinator.data is None:
            return False

        data = self.coordinator.data

        # Determine state based on sensor type
        if self.sensor_type == "system_status":
            # System is OK if no errors in data
            return data.get("system_error", False) is False
        elif self.sensor_type == "redis_connection":
            # Redis is connected if we have valid data
            return data.get("redis_connected", False)
        elif self.sensor_type == "min_valves_ok":
            # Minimum valves requirement is met
            return data.get("min_valves_ok", True)

        return False

    async def async_update(self) -> None:
        """
        Update sensor state from coordinator.

        This is called by Home Assistant when an update is needed.
        The coordinator manages the actual data fetching.
        """
        # Request coordinator to update data
        await self.coordinator.async_request_refresh()
