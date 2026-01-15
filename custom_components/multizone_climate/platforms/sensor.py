"""Sensor platform for Multizone Climate integration."""
from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.sensor import SensorEntity
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
    Set up sensor entities.
    
    Creates sensors for:
    - Main climate current/target temperature
    - Outdoor temperature  
    - Zone satisfaction states
    - Valve states
    - Job status
    - System metrics
    """
    # TODO: Create sensor entities
    # TODO: Call async_add_entities()
    pass


class MultizoneClimateSensor(SensorEntity):
    """Base sensor for multizone climate."""

    def __init__(self, coordinator: Any, sensor_type: str) -> None:
        """
        Initialize sensor.
        
        Args:
            coordinator: Data update coordinator
            sensor_type: Type of sensor
        """
        self.coordinator = coordinator
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return sensor name."""
        # TODO: Return name based on sensor_type
        return f"Multizone {self.sensor_type}"

    @property
    def state(self) -> Any:
        """
        Return sensor state.
        
        Returns:
            State value from coordinator data
        """
        # TODO: Get state from coordinator
        return None

    async def async_update(self) -> None:
        """Update sensor state from coordinator."""
        # TODO: Request coordinator update
        pass
