"""Climate platform for Multizone Climate integration."""

from __future__ import annotations

import hashlib
from typing import Any, Literal, cast
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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
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
    HVAC_ACTION_OFF,
    HVAC_ACTION_COOL,
    HVAC_ACTION_IDLE,
    JOB_TYPE_CALCULATE_MAIN_TEMP,
    JOB_TYPE_UPDATE_VALVES,
)
from .core import ZoneSatisfactionStateMachine

_LOGGER = logging.getLogger(__name__)

# Type alias for HVAC mode literals used by state machine
HVACModeLiteral = Literal["heating", "cooling", "off"]


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
        - Create zone climate entities for each configured zone
        - Each zone is a separate device linked to the main integration device
    """
    # Get coordinator and redis_client from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    redis_client = data["redis_client"]

    entities: list[ClimateEntity] = []

    # Fetch zones from Redis
    zone_ids = await redis_client.get_zone_ids()
    _LOGGER.info(f"Setting up climate platform with {len(zone_ids)} zones from Redis: {zone_ids}")

    # Create ZoneClimateEntity for each zone
    for zone_id in zone_ids:
        zone_config = await redis_client.get_zone_state(zone_id)
        _LOGGER.info(f"Processing zone_id: {zone_id}, zone_config: {zone_config.get('name') if zone_config else 'None'}")
        if zone_config:
            zone_entity = ZoneClimateEntity(
                coordinator=coordinator,
                redis_client=redis_client,
                zone_id=zone_id,
                zone_config=zone_config,
                config_entry=config_entry,
                hass=hass,
            )
            _LOGGER.info(f"Created entity for zone_id: {zone_id}, name: {zone_config.get('name')}")
            entities.append(zone_entity)

    # Add all entities
    async_add_entities(entities)

    _LOGGER.info(
        "Added %d zone climate entities",
        len(entities),
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

        # Zone parameters - these come from Redis as floats/ints via JSON deserialization
        self._target_temperature: float = cast(
            float, zone_config.get("target_temperature", 20.0)
        )
        self._target_change_threshold: float = cast(
            float, zone_config.get("target_change_threshold", 0.1)
        )
        self._opening_offset = zone_config.get("opening_offset", 0.3)
        self._closing_offset = zone_config.get("closing_offset", 0.3)
        self._priority = zone_config.get("priority", 0)
        self._is_fallback = zone_config.get("is_fallback_valve", False)

        # State tracking
        self._enabled = zone_config.get("enabled", "true") not in ["false", "False", "0"]
        self._current_temperature: float | None = cast(
            float | None, zone_config.get("current_temperature")
        )
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
        return cast(str, self._name)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_zone_{self.zone_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, f"zone_{self.zone_id}")},
            "name": f"Multizone Climate - {self._name}",
            "manufacturer": "Multizone Climate",
            "model": "Zone Controller",
            "via_device": (DOMAIN, "main"),
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
            HVACMode: HEAT if enabled, OFF if disabled
        """
        return HVACMode.HEAT if self._enabled else HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """
        Return the list of available HVAC modes.

        Returns:
            list: Available modes (HEAT and OFF)
        """
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """
        Return the list of supported features.

        Returns:
            int: Supported features flags
        """
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

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
        temperature = self._round_to_threshold(temperature)

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

        # Ensure previous temperature is initialized when only target changes
        # This avoids _update_satisfaction_state() early-returning when
        # _previous_temperature is None (e.g. after restart) but we already
        # have a valid _current_temperature.
        if getattr(self, "_previous_temperature", None) is None and getattr(
            self, "_current_temperature", None
        ) is not None:
            self._previous_temperature = self._current_temperature
        # Recalculate satisfaction state immediately with new target bounds
        await self._update_satisfaction_state()

        # Write to Redis (now with correct satisfaction state)
        await self._update_zone_state_in_redis()

        # Trigger recalculation by enqueuing jobs
        # Use milliseconds + zone_id hash for uniqueness to avoid collisions
        job_id_suffix = f"{int(self.hass.loop.time() * 1000)}_{hashlib.md5(self.zone_id.encode()).hexdigest()[:8]}"

        await self.redis_client.enqueue_job(
            JOB_TYPE_CALCULATE_MAIN_TEMP,
            {
                "job_id": f"calc_temp_{self.zone_id}_{job_id_suffix}",
                "trigger": f"zone_{self.zone_id}_target_changed",
                "changed_zones": [self.zone_id],
                "enqueued_at": self.hass.loop.time(),
            },
        )

        await self.redis_client.enqueue_job(
            JOB_TYPE_UPDATE_VALVES,
            {
                "job_id": f"update_valves_{self.zone_id}_{job_id_suffix}",
                "trigger": f"zone_{self.zone_id}_target_changed",
                "changed_zones": [self.zone_id],
                "enqueued_at": self.hass.loop.time(),
            },
        )

        # Update HA state
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """
        Set HVAC mode (HEAT to enable, OFF to disable zone).

        Args:
            hvac_mode: The HVAC mode to set (HEAT or OFF)

        Tasks:
            - Validate fallback zone requirements if disabling
            - Update enabled state
            - Write to Redis
            - Trigger valve update
        """
        if hvac_mode == HVACMode.OFF:
            await self._set_enabled(False)
        elif hvac_mode == HVACMode.HEAT:
            await self._set_enabled(True)
        else:
            _LOGGER.warning(
                "Unsupported HVAC mode %s for zone %s", hvac_mode, self.zone_id
            )

    async def _set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the zone.

        Args:
            enabled: True to enable, False to disable

        Raises:
            ValueError: If disabling would violate minimum valve requirements

        Tasks:
            - Validate minimum fallback zones if disabling
            - Update enabled state
            - Write to Redis
            - Trigger valve update
        """
        # If disabling a fallback zone, validate minimum requirements
        if not enabled and self._is_fallback:
            # Get all zone IDs from Redis
            zone_ids = await self.redis_client.get_zone_ids()

            # Count currently enabled fallback zones (excluding this one)
            enabled_fallback_count = 0
            for zone_id in zone_ids:
                if zone_id == self.zone_id:
                    continue
                zone_state = await self.redis_client.get_zone_state(zone_id)
                if zone_state:
                    is_fallback = zone_state.get("is_fallback_valve", False) not in [False, "false", "False", "0"]
                    is_enabled = zone_state.get("enabled", "true") not in ["false", "False", "0"]
                    if is_fallback and is_enabled:
                        enabled_fallback_count += 1

            # Get minimum requirement
            config = self.coordinator.get_config() or {}
            min_valves_required = config.get("min_valves_open", 1)

            # Check if we would violate the minimum
            if enabled_fallback_count < min_valves_required:
                _LOGGER.error(
                    "Cannot disable fallback zone %s: would have %d fallback zones but need at least %d",
                    self.zone_id,
                    enabled_fallback_count,
                    min_valves_required,
                )
                raise ValueError(
                    f"Cannot disable this fallback zone. At least {min_valves_required} "
                    f"fallback zone(s) must remain enabled for safety."
                )

        # Update enabled state
        old_enabled = self._enabled
        self._enabled = enabled

        _LOGGER.info(
            "Zone %s %s (was %s)",
            self.zone_id,
            "enabled" if enabled else "disabled",
            "enabled" if old_enabled else "disabled",
        )

        # Write to Redis
        await self._update_zone_state_in_redis()

        # Trigger valve update job
        job_id_suffix = f"{int(self.hass.loop.time() * 1000)}_{hashlib.md5(self.zone_id.encode()).hexdigest()[:8]}"

        await self.redis_client.enqueue_job(
            JOB_TYPE_UPDATE_VALVES,
            {
                "job_id": f"update_valves_{self.zone_id}_{job_id_suffix}",
                "trigger": f"zone_{self.zone_id}_{'enabled' if enabled else 'disabled'}",
                "changed_zones": [self.zone_id],
                "enqueued_at": self.hass.loop.time(),
            },
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
            - Check if multizone is enabled
            - If disabled, set satisfaction to "unavailable"
            - If enabled, get HVAC mode from main climate
            - Call state machine to calculate new state
            - Update internal state
        """
        if self._current_temperature is None or self._previous_temperature is None:
            return

        # Check if multizone is enabled
        config = self.coordinator.get_config()
        multizone_enabled = config.get("multizone_enabled", False) if config else False

        # If multizone is disabled, set satisfaction to unavailable
        # Zones control valves individually based on offsets only
        if not multizone_enabled:
            old_satisfaction = self._satisfaction_state
            self._satisfaction_state = "unavailable"
            self._temperature_direction = "stable"

            if old_satisfaction != "unavailable":
                _LOGGER.debug(
                    "Zone %s satisfaction set to unavailable (multizone disabled)",
                    self.zone_id,
                )
            return

        # Get HVAC mode from main climate
        main_climate_data = self.coordinator.get_main_climate_data()
        # Default to heating if main climate data unavailable
        # This is safe as zones will not be actively managed when HVAC is off
        hvac_mode_str = HVAC_ACTION_HEATING

        if main_climate_data:
            hvac_action_str = main_climate_data.get(
                "hvac_action", HVAC_ACTION_HEATING
            ).lower()
            if hvac_action_str in (HVAC_ACTION_COOLING, HVAC_ACTION_COOL):
                hvac_mode_str = HVAC_ACTION_COOLING
            elif hvac_action_str in (HVAC_ACTION_OFF, HVAC_ACTION_IDLE):
                hvac_mode_str = HVAC_ACTION_OFF
            else:
                hvac_mode_str = HVAC_ACTION_HEATING

        # Call state machine with proper HVACMode literal type
        # Use explicit type assertion since we've validated the string
        hvac_mode = cast(HVACModeLiteral, hvac_mode_str)

        new_state, temp_direction = self._state_machine.update_state(
            current_temperature=self._current_temperature,
            previous_temperature=self._previous_temperature,
            current_state=self._satisfaction_state,
            hvac_mode=hvac_mode,
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
            "valve_id": self._valve_switch_entity_id,  # Alias for compatibility with valve controller
            "current_temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "enabled": "true" if self._enabled else "false",
            "satisfaction": self._satisfaction_state,
            "valve_state": self._valve_state,
            "temperature_rising": self._temperature_direction == "rising",
            "temperature_falling": self._temperature_direction == "falling",
            "target_change_threshold": self._target_change_threshold,
            "opening_offset": self._opening_offset,
            "closing_offset": self._closing_offset,
            "is_fallback_valve": self._is_fallback,
            "priority": self._priority,
            "last_updated": dt_util.utcnow().isoformat(),
        }

        await self.redis_client.set_zone_state(self.zone_id, zone_state)

    async def _sync_valve_state_from_ha(self) -> None:
        """
        Sync valve state from Home Assistant entity to Redis.

        This is called on entity initialization to ensure Redis has the
        actual current state of the valve switch.

        Tasks:
            - Read valve switch entity state from HA
            - Map HA state (on/off) to valve state (opened/closed)
            - Update internal state and Redis
        """
        if not self._valve_switch_entity_id:
            return

        valve_state_obj = self.hass.states.get(self._valve_switch_entity_id)
        if valve_state_obj:
            # Map HA state to valve state
            ha_state = valve_state_obj.state
            if ha_state == "on":
                valve_state = "opened"
            elif ha_state == "off":
                valve_state = "closed"
            else:
                # Unknown or unavailable state, keep as unknown
                _LOGGER.debug(
                    "Valve switch %s has state %s, keeping valve_state as %s",
                    self._valve_switch_entity_id,
                    ha_state,
                    self._valve_state,
                )
                return

            # Update internal state
            old_valve_state = self._valve_state
            self._valve_state = valve_state

            # Update Redis
            await self._update_zone_state_in_redis()

            _LOGGER.debug(
                "Synced valve state for zone %s from HA entity %s: %s -> %s",
                self.zone_id,
                self._valve_switch_entity_id,
                old_valve_state,
                valve_state,
            )
        else:
            _LOGGER.warning(
                "Valve switch entity %s not found for zone %s during state sync",
                self._valve_switch_entity_id,
                self.zone_id,
            )

    def _round_to_threshold(self, temperature: float) -> float:
        """
        Round temperature to target change threshold and clamp to min/max.

        Args:
            temperature: Temperature to round

        Returns:
            float: Rounded and clamped temperature

        Note:
            Floating-point arithmetic may introduce minor precision errors,
            but these are acceptable for temperature control (< 0.001°C).
        """
        # Round to target change threshold
        temperature = (
            round(temperature / self._target_change_threshold)
            * self._target_change_threshold
        )
        # Clamp to min/max
        return max(self.min_temp, min(self.max_temp, temperature))

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

        # Sync valve state from HA entity to Redis
        await self._sync_valve_state_from_ha()
