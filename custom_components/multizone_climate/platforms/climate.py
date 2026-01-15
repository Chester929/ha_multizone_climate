"""Climate platform for Multizone Climate integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DOMAIN,
    ATTR_SATISFACTION,
    ATTR_VALVE_STATE,
    ATTR_TEMPERATURE_RISING,
    ATTR_TEMPERATURE_FALLING,
    ATTR_PRIORITY,
    ATTR_IS_FALLBACK,
    ATTR_OUTDOOR_TEMPERATURE,
    ATTR_MULTIZONE_ENABLED,
    STATE_UNKNOWN,
    HVAC_ACTION_HEATING,
    HVAC_ACTION_COOLING,
    HVAC_ACTION_IDLE,
    HVAC_ACTION_OFF,
    JOB_TYPE_CALCULATE_MAIN_TEMP,
    JOB_TYPE_UPDATE_VALVES,
)
from ..core import ZoneSatisfactionStateMachine

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up climate entities from a config entry.
    
    Args:
        hass: Home Assistant instance
        config_entry: Config entry for this integration
        async_add_entities: Callback to add entities
    
    Tasks:
        - Create main climate device entity
        - Create zone climate entities for each configured zone
    """
    # Get coordinator and redis_client from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    redis_client = data["redis_client"]
    
    # Get config from coordinator
    config = coordinator.get_config()
    if not config:
        _LOGGER.warning("No config found in coordinator, cannot create climate entities")
        return
    
    # Create main climate device entity
    main_climate = MainClimateDevice(
        coordinator=coordinator,
        redis_client=redis_client,
        config=config,
        config_entry=config_entry,
    )
    
    entities = [main_climate]
    
    # Fetch zones from Redis
    zone_ids = await redis_client.get_zone_ids()
    
    # Create ZoneClimateEntity for each zone
    for zone_id in zone_ids:
        zone_config = await redis_client.get_zone_state(zone_id)
        if zone_config:
            zone_entity = ZoneClimateEntity(
                coordinator=coordinator,
                redis_client=redis_client,
                zone_id=zone_id,
                zone_config=zone_config,
                config_entry=config_entry,
                hass=hass,
            )
            entities.append(zone_entity)
    
    # Add all entities
    async_add_entities(entities)
    
    _LOGGER.info(
        "Added %d climate entities (%d zones + 1 main device)",
        len(entities),
        len(zone_ids),
    )


class MainClimateDevice(ClimateEntity):
    """
    Main climate device entity.
    
    Represents the integration itself and the main HVAC thermostat.
    Displays:
    - Current and target temperatures
    - Outdoor temperature
    - HVAC mode and action
    - Multizone enable status
    
    NOTE: This entity is read-only - actual control is via the main thermostat entity.
    """

    def __init__(
        self,
        coordinator: Any,
        redis_client: Any,
        config: dict,
        config_entry: ConfigEntry,
    ) -> None:
        """
        Initialize main climate device.
        
        Args:
            coordinator: Data update coordinator
            redis_client: Redis client
            config: Integration configuration
            config_entry: Config entry for device info
        """
        self.coordinator = coordinator
        self.redis_client = redis_client
        self.config = config
        self._config_entry = config_entry
        self._attr_should_poll = False
        
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Multizone Climate Main"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_main_{self._config_entry.entry_id}"

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Multizone Climate",
            "manufacturer": "Multizone Climate",
            "model": "Main Controller",
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """
        Return the current temperature.
        
        Returns:
            float: Current temperature from main climate entity
        """
        data = self.coordinator.get_main_climate_data()
        if data:
            return data.get("current_temperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """
        Return the target temperature.
        
        Returns:
            float: Target temperature of main climate entity (calculated)
        """
        data = self.coordinator.get_main_climate_data()
        if data:
            return data.get("target_temperature")
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """
        Return the current HVAC mode.
        
        Returns:
            HVACMode: Current HVAC mode (heat/cool/off)
        """
        data = self.coordinator.get_main_climate_data()
        if not data:
            return None
            
        hvac_mode_str = data.get("hvac_mode", "").lower()
        
        # Map from main climate entity mode
        if hvac_mode_str in ("heat", "manual", "heating"):
            return HVACMode.HEAT
        elif hvac_mode_str in ("cool", "cooling"):
            return HVACMode.COOL
        elif hvac_mode_str in ("off", "anti-freeze"):
            return HVACMode.OFF
        
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """
        Return the list of available HVAC modes.
        
        Returns:
            list: Available modes (read-only, reflects main climate)
        """
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def hvac_action(self) -> HVACAction | None:
        """
        Return the current HVAC action.
        
        Returns:
            HVACAction: Current action (heating/cooling/idle/off)
        """
        data = self.coordinator.get_main_climate_data()
        if not data:
            return None
            
        hvac_action_str = data.get("hvac_action", "").lower()
        
        if hvac_action_str == "heating":
            return HVACAction.HEATING
        elif hvac_action_str == "cooling":
            return HVACAction.COOLING
        elif hvac_action_str == "idle":
            return HVACAction.IDLE
        elif hvac_action_str == "off":
            return HVACAction.OFF
        
        return HVACAction.IDLE

    @property
    def supported_features(self) -> int:
        """
        Return the supported features.
        
        Returns:
            int: Feature flags (read-only, no target temperature control)
        """
        # Main climate is read-only - control via main thermostat entity
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return extra state attributes.
        
        Returns:
            dict: Additional attributes including outdoor temp and multizone status
        """
        data = self.coordinator.get_main_climate_data()
        if not data:
            return {}
        
        return {
            ATTR_OUTDOOR_TEMPERATURE: data.get("outdoor_temperature"),
            ATTR_MULTIZONE_ENABLED: data.get("multizone_enabled", False),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )


class ZoneClimateEntity(ClimateEntity):
    """
    Climate entity for a single zone.
    
    Represents one room/zone with:
    - Temperature sensor
    - Valve switch
    - Target temperature control
    - Satisfaction state calculation
    - Temperature direction tracking
    
    Responsibilities:
    - Read temperature from sensor
    - Store and manage target temperature
    - Calculate satisfaction state with hysteresis
    - Track temperature direction
    - Write state to Redis immediately upon changes
    """

    def __init__(
        self,
        coordinator: Any,
        redis_client: Any,
        zone_id: str,
        zone_config: dict,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """
        Initialize zone climate entity.
        
        Args:
            coordinator: Data update coordinator
            redis_client: Redis client
            zone_id: Zone identifier
            zone_config: Zone configuration
            config_entry: Config entry for device info
            hass: Home Assistant instance
        """
        self.coordinator = coordinator
        self.redis_client = redis_client
        self.zone_id = zone_id
        self.zone_config = zone_config
        self._config_entry = config_entry
        self.hass = hass
        self._attr_should_poll = False
        
        # Extract zone configuration
        self._name = zone_config.get("name", f"Zone {zone_id}")
        self._temp_sensor_entity_id = zone_config.get("temperature_sensor_entity_id")
        self._valve_switch_entity_id = zone_config.get("valve_switch_entity_id")
        
        # Zone parameters
        self._target_temperature = zone_config.get("target_temperature", 20.0)
        self._target_change_threshold = zone_config.get("target_change_threshold", 0.1)
        self._opening_offset = zone_config.get("opening_offset", 0.3)
        self._closing_offset = zone_config.get("closing_offset", 0.3)
        self._priority = zone_config.get("priority", 0)
        self._is_fallback = zone_config.get("is_fallback_valve", False)
        
        # State tracking
        self._current_temperature: float | None = zone_config.get("current_temperature")
        self._previous_temperature: float | None = self._current_temperature
        self._satisfaction_state = zone_config.get("satisfaction", STATE_UNKNOWN)
        self._temperature_direction = "stable"
        self._valve_state = zone_config.get("valve_state", "closed")
        
        # Initialize state machine
        global_config = coordinator.get_config() or {}
        satisfaction_eps = global_config.get("satisfaction_eps", 0.0)
        
        self._state_machine = ZoneSatisfactionStateMachine(
            target_temperature=self._target_temperature,
            opening_offset=self._opening_offset,
            closing_offset=self._closing_offset,
            satisfaction_eps=satisfaction_eps,
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_zone_{self.zone_id}"

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Multizone Climate",
            "manufacturer": "Multizone Climate",
            "model": "Main Controller",
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """
        Return the current temperature.
        
        Returns:
            float: Current temperature from zone sensor
        """
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """
        Return the target temperature.
        
        Returns:
            float: Zone target temperature
        """
        return self._target_temperature

    @property
    def target_temperature_step(self) -> float:
        """
        Return the target temperature step.
        
        Returns:
            float: Step size for target temperature changes
        """
        return self._target_change_threshold

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 35.0

    @property
    def hvac_mode(self) -> HVACMode:
        """
        Return the current HVAC mode.
        
        Returns:
            HVACMode: Always HEAT (zones don't control mode)
        """
        # Zones are always in HEAT mode (or follow main climate)
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """
        Return the list of available HVAC modes.
        
        Returns:
            list: Available modes
        """
        return [HVACMode.HEAT]

    @property
    def supported_features(self) -> int:
        """
        Return the list of supported features.
        
        Returns:
            int: Supported features flags
        """
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """
        Set new target temperature.
        
        Args:
            **kwargs: Service call parameters with ATTR_TEMPERATURE
        
        Tasks:
            - Update target in zone state
            - Write to Redis
            - Trigger recalculation automation
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("No temperature provided to set_temperature")
            return
        
        # Round to target change threshold
        temperature = round(temperature / self._target_change_threshold) * self._target_change_threshold
        
        # Clamp to min/max
        temperature = max(self.min_temp, min(self.max_temp, temperature))
        
        _LOGGER.debug(
            "Setting target temperature for zone %s to %.1f°C",
            self.zone_id,
            temperature,
        )
        
        # Update internal state
        self._target_temperature = temperature
        
        # Update state machine with new target
        self._state_machine = ZoneSatisfactionStateMachine(
            target_temperature=self._target_temperature,
            opening_offset=self._opening_offset,
            closing_offset=self._closing_offset,
            satisfaction_eps=self._state_machine.satisfaction_eps,
        )
        
        # Write to Redis
        await self._update_zone_state_in_redis()
        
        # Trigger recalculation by enqueuing jobs
        job_id_suffix = int(self.hass.loop.time())
        
        await self.redis_client.enqueue_job(
            JOB_TYPE_CALCULATE_MAIN_TEMP,
            {
                "job_id": f"calc_temp_{self.zone_id}_{job_id_suffix}",
                "trigger": f"zone_{self.zone_id}_target_changed",
                "changed_zones": [self.zone_id],
                "enqueued_at": self.hass.loop.time(),
            }
        )
        
        await self.redis_client.enqueue_job(
            JOB_TYPE_UPDATE_VALVES,
            {
                "job_id": f"update_valves_{self.zone_id}_{job_id_suffix}",
                "trigger": f"zone_{self.zone_id}_target_changed",
                "changed_zones": [self.zone_id],
                "enqueued_at": self.hass.loop.time(),
            }
        )
        
        # Update HA state
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """
        Handle coordinator update.
        
        Tasks:
            - Read temperature from sensor
            - Calculate satisfaction state
            - Update temperature direction
            - Write state to Redis
        """
        self.hass.async_create_task(self._async_update_from_sensor())

    async def _async_update_from_sensor(self) -> None:
        """
        Update entity state from temperature sensor.
        
        Tasks:
            - Read current temp from sensor entity
            - Get previous temp from state
            - Call state machine to update satisfaction
            - Write to Redis
        """
        # Read current temperature from sensor entity
        if self._temp_sensor_entity_id:
            sensor_state = self.hass.states.get(self._temp_sensor_entity_id)
            if sensor_state and sensor_state.state not in ("unknown", "unavailable"):
                try:
                    new_temp = float(sensor_state.state)
                    
                    # Only update if temperature actually changed
                    if new_temp != self._current_temperature:
                        # Store previous temperature
                        self._previous_temperature = self._current_temperature
                        self._current_temperature = new_temp
                        
                        # Update satisfaction state using state machine
                        await self._update_satisfaction_state()
                        
                        # Write updated state to Redis
                        await self._update_zone_state_in_redis()
                        
                        # Update HA state
                        self.async_write_ha_state()
                        
                except ValueError:
                    _LOGGER.warning(
                        "Invalid temperature value for zone %s: %s",
                        self.zone_id,
                        sensor_state.state,
                    )

    async def _update_satisfaction_state(self) -> None:
        """
        Update satisfaction state using state machine.
        
        Tasks:
            - Get HVAC mode from main climate
            - Call state machine to calculate new state
            - Update internal state
        """
        if self._current_temperature is None or self._previous_temperature is None:
            return
        
        # Get HVAC mode from main climate
        main_climate_data = self.coordinator.get_main_climate_data()
        hvac_action = "heating"  # Default
        
        if main_climate_data:
            hvac_action_str = main_climate_data.get("hvac_action", "heating").lower()
            if hvac_action_str in ("cooling", "cool"):
                hvac_action = "cooling"
            elif hvac_action_str in ("off", "idle"):
                hvac_action = "off"
        
        # Call state machine
        new_state, temp_direction = self._state_machine.update_state(
            current_temperature=self._current_temperature,
            previous_temperature=self._previous_temperature,
            current_state=self._satisfaction_state,
            hvac_mode=hvac_action,
        )
        
        # Update internal state
        old_satisfaction = self._satisfaction_state
        self._satisfaction_state = new_state
        self._temperature_direction = temp_direction
        
        # Log state changes
        if old_satisfaction != new_state:
            _LOGGER.debug(
                "Zone %s satisfaction changed: %s -> %s (temp: %.1f°C, direction: %s)",
                self.zone_id,
                old_satisfaction,
                new_state,
                self._current_temperature,
                temp_direction,
            )

    async def _update_zone_state_in_redis(self) -> None:
        """
        Write zone state to Redis.
        
        Tasks:
            - Build zone state dict
            - Write to Redis
            - Update timestamp
        """
        zone_state = {
            "id": self.zone_id,
            "name": self._name,
            "temperature_sensor_entity_id": self._temp_sensor_entity_id,
            "valve_switch_entity_id": self._valve_switch_entity_id,
            "current_temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "state": "ON",  # Zones are always ON once created; OFF zones are removed
            "satisfaction": self._satisfaction_state,
            "valve_state": self._valve_state,
            "temperature_rising": self._temperature_direction == "rising",
            "temperature_falling": self._temperature_direction == "falling",
            "target_change_threshold": self._target_change_threshold,
            "opening_offset": self._opening_offset,
            "closing_offset": self._closing_offset,
            "is_fallback_valve": self._is_fallback,
            "priority": self._priority,
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        await self.redis_client.set_zone_state(self.zone_id, zone_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return extra state attributes.
        
        Returns:
            dict: Additional attributes:
                - satisfaction: Satisfaction state
                - valve_state: Current valve state
                - temperature_rising: Is temperature rising
                - temperature_falling: Is temperature falling
                - priority: Zone priority
                - is_fallback_valve: Is fallback valve
        """
        return {
            ATTR_SATISFACTION: self._satisfaction_state,
            ATTR_VALVE_STATE: self._valve_state,
            ATTR_TEMPERATURE_RISING: self._temperature_direction == "rising",
            ATTR_TEMPERATURE_FALLING: self._temperature_direction == "falling",
            ATTR_PRIORITY: self._priority,
            ATTR_IS_FALLBACK: self._is_fallback,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Register coordinator listener
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        
        # Initial update from sensor
        await self._async_update_from_sensor()
