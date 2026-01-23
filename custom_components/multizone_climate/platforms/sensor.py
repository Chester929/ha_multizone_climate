"""Sensor platform for Multizone Climate integration."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.sensor import (  # type: ignore[import-not-found]
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry  # type: ignore[import-not-found]
from homeassistant.const import UnitOfTemperature  # type: ignore[import-not-found]
from homeassistant.core import HomeAssistant, callback  # type: ignore[import-not-found]
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore[import-not-found]

from ..const import DOMAIN

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
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    redis_client = data["redis_client"]

    entities = []

    # Temperature sensors
    entities.extend(
        [
            MultizoneTemperatureSensor(coordinator, "main_current_temperature"),
            MultizoneTemperatureSensor(coordinator, "main_target_temperature"),
            MultizoneTemperatureSensor(coordinator, "outdoor_temperature"),
        ]
    )

    # System sensors
    entities.extend(
        [
            MultizoneTextSensor(coordinator, "open_valve_count"),
            MultizoneTextSensor(coordinator, "calculate_queue_size"),
            MultizoneTextSensor(coordinator, "valve_queue_size"),
        ]
    )

    # Fetch zones from Redis
    zone_ids = await redis_client.get_zone_ids()

    # Create per-zone sensors
    for zone_id in zone_ids:
        zone_config = await redis_client.get_zone_state(zone_id)
        if zone_config:
            zone_name = zone_config.get("name", f"Zone {zone_id}")
            entities.extend(
                [
                    ZoneTemperatureSensor(
                        coordinator, zone_id, zone_name, "current_temperature"
                    ),
                    ZoneTemperatureSensor(
                        coordinator, zone_id, zone_name, "target_temperature"
                    ),
                    ZoneTextSensor(coordinator, zone_id, zone_name, "satisfaction"),
                    ZoneTextSensor(coordinator, zone_id, zone_name, "valve_state"),
                    ZoneTextSensor(coordinator, zone_id, zone_name, "direction"),
                ]
            )

    async_add_entities(entities)


class MultizoneTemperatureSensor(SensorEntity):
    """Temperature sensor for multizone climate."""

    def __init__(self, coordinator: Any, sensor_type: str) -> None:
        """
        Initialize temperature sensor.

        Args:
            coordinator: Data update coordinator
            sensor_type: Type of sensor (main_current_temperature, main_target_temperature, outdoor_temperature)
        """
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_should_poll = False

        # Set name based on sensor type
        type_names = {
            "main_current_temperature": "Main Current Temperature",
            "main_target_temperature": "Main Target Temperature",
            "outdoor_temperature": "Outdoor Temperature",
        }
        self._attr_name = type_names.get(sensor_type, f"Multizone {sensor_type}")

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, "multizone_climate_main")},
            "name": "Multizone Climate",
            "manufacturer": "Chester929",
            "model": "Multizone Climate Controller",
        }

    @property
    def native_value(self) -> float | None:
        """
        Return sensor state.

        Returns:
            State value from coordinator data
        """
        if not self.coordinator.data:
            return None

        main_climate = self.coordinator.data.get("main_climate", {})

        if self.sensor_type == "main_current_temperature":
            return float(main_climate.get("current_temperature")) if main_climate.get("current_temperature") is not None else None
        if self.sensor_type == "main_target_temperature":
            return float(main_climate.get("target_temperature")) if main_climate.get("target_temperature") is not None else None
        if self.sensor_type == "outdoor_temperature":
            return float(main_climate.get("outdoor_temperature")) if main_climate.get("outdoor_temperature") is not None else None

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )


class MultizoneTextSensor(SensorEntity):
    """Text/count sensor for multizone climate."""

    def __init__(self, coordinator: Any, sensor_type: str) -> None:
        """
        Initialize text sensor.

        Args:
            coordinator: Data update coordinator
            sensor_type: Type of sensor
        """
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_should_poll = False

        # Set name based on sensor type
        type_names = {
            "open_valve_count": "Open Valve Count",
            "calculate_queue_size": "Calculate Job Queue Size",
            "valve_queue_size": "Valve Job Queue Size",
        }
        self._attr_name = type_names.get(sensor_type, f"Multizone {sensor_type}")

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, "multizone_climate_main")},
            "name": "Multizone Climate",
            "manufacturer": "Chester929",
            "model": "Multizone Climate Controller",
        }

    @property
    def native_value(self) -> Any:
        """
        Return sensor state.

        Returns:
            State value from coordinator data
        """
        if not self.coordinator.data:
            return None

        if self.sensor_type == "open_valve_count":
            # Count open valves from zones
            zones = self.coordinator.data.get("zones", {})
            return sum(
                1 for zone in zones.values() if zone.get("valve_state") == "open"
            )
        if self.sensor_type == "calculate_queue_size":
            # Return cached queue size from coordinator data
            return self.coordinator.data.get("calculate_queue_size", 0)
        if self.sensor_type == "valve_queue_size":
            # Return cached queue size from coordinator data
            return self.coordinator.data.get("valve_queue_size", 0)

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )


class ZoneTemperatureSensor(SensorEntity):
    """Temperature sensor for a specific zone."""

    def __init__(
        self, coordinator: Any, zone_id: str, zone_name: str, sensor_type: str
    ) -> None:
        """
        Initialize zone temperature sensor.

        Args:
            coordinator: Data update coordinator
            zone_id: Zone identifier
            zone_name: Zone display name
            sensor_type: Type of sensor (current_temperature, target_temperature)
        """
        self.coordinator = coordinator
        self.zone_id = zone_id
        self.zone_name = zone_name
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_zone_{zone_id}_{sensor_type}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_should_poll = False

        # Set name based on sensor type
        type_names = {
            "current_temperature": "Current Temperature",
            "target_temperature": "Target Temperature",
        }
        self._attr_name = f"{zone_name} {type_names.get(sensor_type, sensor_type)}"

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, f"zone_{self.zone_id}")},
            "name": self.zone_name,
            "manufacturer": "Chester929",
            "model": "Multizone Climate Zone",
            "via_device": (DOMAIN, "multizone_climate_main"),
        }

    @property
    def native_value(self) -> float | None:
        """
        Return sensor state.

        Returns:
            State value from coordinator data
        """
        zone_data = self.coordinator.get_zone_data(self.zone_id)
        if not zone_data:
            return None

        value = zone_data.get(self.sensor_type)
        return float(value) if value is not None else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )


class ZoneTextSensor(SensorEntity):
    """Text sensor for a specific zone."""

    def __init__(
        self, coordinator: Any, zone_id: str, zone_name: str, sensor_type: str
    ) -> None:
        """
        Initialize zone text sensor.

        Args:
            coordinator: Data update coordinator
            zone_id: Zone identifier
            zone_name: Zone display name
            sensor_type: Type of sensor (satisfaction, valve_state, direction)
        """
        self.coordinator = coordinator
        self.zone_id = zone_id
        self.zone_name = zone_name
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_zone_{zone_id}_{sensor_type}"
        self._attr_should_poll = False

        # Set name based on sensor type
        type_names = {
            "satisfaction": "Satisfaction State",
            "valve_state": "Valve State",
            "direction": "Temperature Direction",
        }
        self._attr_name = f"{zone_name} {type_names.get(sensor_type, sensor_type)}"

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, f"zone_{self.zone_id}")},
            "name": self.zone_name,
            "manufacturer": "Chester929",
            "model": "Multizone Climate Zone",
            "via_device": (DOMAIN, "multizone_climate_main"),
        }

    @property
    def native_value(self) -> str | None:
        """
        Return sensor state.

        Returns:
            State value from coordinator data
        """
        zone_data = self.coordinator.get_zone_data(self.zone_id)
        if not zone_data:
            return None

        if self.sensor_type == "satisfaction":
            value = zone_data.get("satisfaction_state")
            return str(value) if value is not None else None
        if self.sensor_type == "valve_state":
            value = zone_data.get("valve_state")
            return str(value) if value is not None else None
        if self.sensor_type == "direction":
            # Determine direction from temperature_rising and temperature_falling
            if zone_data.get("temperature_rising"):
                return "rising"
            if zone_data.get("temperature_falling"):
                return "falling"
            return "stable"

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
