"""Config flow for Multizone Climate integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    DOMAIN,
    CONF_REDIS_HOST,
    CONF_REDIS_PORT,
    CONF_REDIS_PASSWORD,
    CONF_REDIS_DB,
    CONF_REDIS_KEY_PREFIX,
    CONF_MAIN_CLIMATE_ENTITY,
    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
    CONF_USE_AVERAGE_MODE,
    CONF_MIN_VALVES_OPEN,
    CONF_MAIN_MIN_TEMP,
    CONF_MAIN_MAX_TEMP,
    CONF_MAIN_CHANGE_THRESHOLD,
    CONF_VALVE_ACTUATION_DELAY,
    CONF_COORDINATOR_INTERVAL,
    CONF_SATISFACTION_EPS,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMP_SENSOR,
    CONF_ZONE_VALVE_SWITCH,
    CONF_ZONE_TARGET_THRESHOLD,
    CONF_ZONE_OPENING_OFFSET,
    CONF_ZONE_CLOSING_OFFSET,
    CONF_ZONE_IS_FALLBACK,
    CONF_ZONE_PRIORITY,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_KEY_PREFIX,
    DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
    DEFAULT_USE_AVERAGE_MODE,
    DEFAULT_MIN_VALVES_OPEN,
    DEFAULT_MAIN_MIN_TEMP,
    DEFAULT_MAIN_MAX_TEMP,
    DEFAULT_MAIN_CHANGE_THRESHOLD,
    DEFAULT_VALVE_ACTUATION_DELAY,
    DEFAULT_COORDINATOR_INTERVAL,
    DEFAULT_SATISFACTION_EPS,
    DEFAULT_ZONE_TARGET_THRESHOLD,
    DEFAULT_ZONE_OPENING_OFFSET,
    DEFAULT_ZONE_CLOSING_OFFSET,
    DEFAULT_ZONE_IS_FALLBACK,
    DEFAULT_ZONE_PRIORITY,
)
from .core.redis_client import RedisClient

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multizone Climate."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle the initial step - Redis configuration.

        Args:
            user_input: User provided configuration data

        Returns:
            FlowResult: Either show form or proceed to next step
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate Redis connection
            try:
                redis_client = RedisClient(
                    host=user_input[CONF_REDIS_HOST],
                    port=user_input[CONF_REDIS_PORT],
                    password=user_input.get(CONF_REDIS_PASSWORD),
                    db=user_input[CONF_REDIS_DB],
                    key_prefix=user_input[CONF_REDIS_KEY_PREFIX],
                )
                await redis_client.connect()
                await redis_client.disconnect()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during Redis validation: %s", err)
                errors["base"] = "unknown"
            else:
                # Store Redis configuration
                self._data.update(user_input)
                return await self.async_step_main_climate()

        # Show form with Redis fields
        data_schema = vol.Schema(
            {
                vol.Required(CONF_REDIS_HOST, default=DEFAULT_REDIS_HOST): str,
                vol.Required(CONF_REDIS_PORT, default=DEFAULT_REDIS_PORT): int,
                vol.Optional(CONF_REDIS_PASSWORD): str,
                vol.Required(CONF_REDIS_DB, default=DEFAULT_REDIS_DB): int,
                vol.Required(
                    CONF_REDIS_KEY_PREFIX, default=DEFAULT_REDIS_KEY_PREFIX
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_main_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle main climate entity selection.

        Args:
            user_input: User selected main climate entity

        Returns:
            FlowResult: Either show form or proceed to automation config
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entity exists and is a climate entity
            entity_id = user_input[CONF_MAIN_CLIMATE_ENTITY]
            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(entity_id)

            if entity_entry is None:
                errors["base"] = "invalid_entity"
            elif not entity_id.startswith("climate."):
                errors["base"] = "not_climate_entity"
            else:
                # Check if already configured
                await self.async_set_unique_id(entity_id)
                self._abort_if_unique_id_configured()

                # Store main climate entity
                self._data.update(user_input)
                return await self.async_step_automation_config()

        # Show entity selector for climate domain
        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAIN_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate"),
                ),
            }
        )

        return self.async_show_form(
            step_id="main_climate",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_automation_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle automation configuration.

        Args:
            user_input: User provided automation settings

        Returns:
            FlowResult: Create config entry
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate parameter ranges
            if user_input[CONF_MAIN_MIN_TEMP] >= user_input[CONF_MAIN_MAX_TEMP]:
                errors["base"] = "invalid_temp_range"
            elif user_input[CONF_MIN_VALVES_OPEN] < 1:
                errors["base"] = "invalid_min_valves"
            elif (
                not user_input[CONF_USE_AVERAGE_MODE]
                and not 0 <= user_input[CONF_MAIN_TARGET_ALL_ZONES_SATISFIED] <= 1
            ):
                errors["base"] = "invalid_slider_value"
            else:
                # Merge all collected data
                self._data.update(user_input)

                # Create config entry
                return self.async_create_entry(
                    title=f"Multizone Climate ({self._data[CONF_MAIN_CLIMATE_ENTITY]})",
                    data=self._data,
                )

        # Determine defaults from stored data or constants
        use_average_mode = self._data.get(
            CONF_USE_AVERAGE_MODE, DEFAULT_USE_AVERAGE_MODE
        )

        # Show form with automation parameters
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USE_AVERAGE_MODE,
                    default=use_average_mode,
                ): bool,
                vol.Optional(
                    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    default=DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.05,
                        mode=selector.NumberSelectorMode.SLIDER,
                    ),
                ),
                vol.Required(
                    CONF_MIN_VALVES_OPEN,
                    default=DEFAULT_MIN_VALVES_OPEN,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_MIN_TEMP,
                    default=DEFAULT_MAIN_MIN_TEMP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0,
                        max=30.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_MAX_TEMP,
                    default=DEFAULT_MAIN_MAX_TEMP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15.0,
                        max=35.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_CHANGE_THRESHOLD,
                    default=DEFAULT_MAIN_CHANGE_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_VALVE_ACTUATION_DELAY,
                    default=DEFAULT_VALVE_ACTUATION_DELAY,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=300,
                        step=10,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_COORDINATOR_INTERVAL,
                    default=DEFAULT_COORDINATOR_INTERVAL,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=60,
                        step=5,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_SATISFACTION_EPS,
                    default=DEFAULT_SATISFACTION_EPS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="automation_config",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MultizoneClimateOptionsFlow:
        """
        Get the options flow for this handler.

        Args:
            config_entry: Config entry for which to create options flow

        Returns:
            MultizoneClimateOptionsFlow: Options flow handler
        """
        return MultizoneClimateOptionsFlow(config_entry)


class MultizoneClimateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Multizone Climate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """
        Initialize options flow.

        Args:
            config_entry: Config entry to manage options for
        """
        self.config_entry = config_entry
        self._zones: dict[str, Any] = {}
        self._selected_zone_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manage the options.

        Args:
            user_input: User provided options

        Returns:
            FlowResult: Show options menu
        """
        return self.async_show_menu(
            step_id="init",
            menu_options=["config", "zones"],
        )

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Edit configuration options.

        Args:
            user_input: Updated configuration

        Returns:
            FlowResult: Show form or update entry
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate parameter ranges
            if user_input[CONF_MAIN_MIN_TEMP] >= user_input[CONF_MAIN_MAX_TEMP]:
                errors["base"] = "invalid_temp_range"
            elif user_input[CONF_MIN_VALVES_OPEN] < 1:
                errors["base"] = "invalid_min_valves"
            elif (
                not user_input[CONF_USE_AVERAGE_MODE]
                and not 0 <= user_input[CONF_MAIN_TARGET_ALL_ZONES_SATISFIED] <= 1
            ):
                errors["base"] = "invalid_slider_value"
            else:
                # Update config entry data
                new_data = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                # Update Redis config
                try:
                    redis_client = self._get_redis_client()
                    await redis_client.connect()
                    await redis_client.set_config(user_input)
                    await redis_client.disconnect()
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Failed to update Redis config: %s", err)
                    errors["base"] = "redis_update_failed"
                else:
                    return self.async_create_entry(title="", data={})

        # Get current values
        current_data = self.config_entry.data
        use_average_mode = current_data.get(
            CONF_USE_AVERAGE_MODE, DEFAULT_USE_AVERAGE_MODE
        )

        # Show config edit form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USE_AVERAGE_MODE,
                    default=use_average_mode,
                ): bool,
                vol.Optional(
                    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    default=current_data.get(
                        CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                        DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.05,
                        mode=selector.NumberSelectorMode.SLIDER,
                    ),
                ),
                vol.Required(
                    CONF_MIN_VALVES_OPEN,
                    default=current_data.get(
                        CONF_MIN_VALVES_OPEN, DEFAULT_MIN_VALVES_OPEN
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_MIN_TEMP,
                    default=current_data.get(CONF_MAIN_MIN_TEMP, DEFAULT_MAIN_MIN_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0,
                        max=30.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_MAX_TEMP,
                    default=current_data.get(CONF_MAIN_MAX_TEMP, DEFAULT_MAIN_MAX_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=15.0,
                        max=35.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_MAIN_CHANGE_THRESHOLD,
                    default=current_data.get(
                        CONF_MAIN_CHANGE_THRESHOLD, DEFAULT_MAIN_CHANGE_THRESHOLD
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_VALVE_ACTUATION_DELAY,
                    default=current_data.get(
                        CONF_VALVE_ACTUATION_DELAY, DEFAULT_VALVE_ACTUATION_DELAY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=300,
                        step=10,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_COORDINATOR_INTERVAL,
                    default=current_data.get(
                        CONF_COORDINATOR_INTERVAL, DEFAULT_COORDINATOR_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=60,
                        step=5,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_SATISFACTION_EPS,
                    default=current_data.get(
                        CONF_SATISFACTION_EPS, DEFAULT_SATISFACTION_EPS
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="config",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manage climate zones.

        Args:
            user_input: Zone management action

        Returns:
            FlowResult: Show zone management interface
        """
        return self.async_show_menu(
            step_id="zones",
            menu_options=["add_zone", "edit_zone", "delete_zone"],
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Add a new climate zone.

        Args:
            user_input: New zone configuration

        Returns:
            FlowResult: Show form or create zone
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entities exist
            temp_sensor = user_input[CONF_ZONE_TEMP_SENSOR]
            valve_switch = user_input[CONF_ZONE_VALVE_SWITCH]

            registry = er.async_get(self.hass)
            temp_entity = registry.async_get(temp_sensor)
            valve_entity = registry.async_get(valve_switch)

            if temp_entity is None:
                errors["base"] = "invalid_temp_sensor"
            elif valve_entity is None:
                errors["base"] = "invalid_valve_switch"
            elif not temp_sensor.startswith("sensor."):
                errors["base"] = "not_sensor_entity"
            elif not valve_switch.startswith("switch."):
                errors["base"] = "not_switch_entity"
            else:
                # Create zone
                try:
                    redis_client = self._get_redis_client()
                    await redis_client.connect()

                    # Generate zone ID from name
                    zone_id = (
                        f"zone_{user_input[CONF_ZONE_NAME].lower().replace(' ', '_')}"
                    )

                    # Check if zone already exists
                    existing_zone_ids = await redis_client.get_zone_ids()
                    if zone_id in existing_zone_ids:
                        errors["base"] = "zone_already_exists"
                    else:
                        # Create zone data
                        zone_data = {
                            "id": zone_id,
                            "name": user_input[CONF_ZONE_NAME],
                            "temperature_sensor_entity_id": temp_sensor,
                            "valve_switch_entity_id": valve_switch,
                            "target_change_threshold": user_input[
                                CONF_ZONE_TARGET_THRESHOLD
                            ],
                            "opening_offset": user_input[CONF_ZONE_OPENING_OFFSET],
                            "closing_offset": user_input[CONF_ZONE_CLOSING_OFFSET],
                            "is_fallback_valve": user_input[CONF_ZONE_IS_FALLBACK],
                            "priority": user_input[CONF_ZONE_PRIORITY],
                            "state": "OFF",
                            "current_temperature": None,
                            "target_temperature": 20.0,
                            "satisfaction": "unknown",
                            "valve_state": "closed",
                            "temperature_rising": False,
                            "temperature_falling": False,
                        }

                        # Store in Redis
                        await redis_client.add_zone(zone_id, zone_data)
                        await redis_client.disconnect()

                        return self.async_create_entry(title="", data={})

                    await redis_client.disconnect()

                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Failed to create zone: %s", err)
                    errors["base"] = "create_zone_failed"

        # Show zone add form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_NAME): str,
                vol.Required(CONF_ZONE_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Required(CONF_ZONE_VALVE_SWITCH): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch"),
                ),
                vol.Required(
                    CONF_ZONE_TARGET_THRESHOLD,
                    default=DEFAULT_ZONE_TARGET_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=1.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_ZONE_OPENING_OFFSET,
                    default=DEFAULT_ZONE_OPENING_OFFSET,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_ZONE_CLOSING_OFFSET,
                    default=DEFAULT_ZONE_CLOSING_OFFSET,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    CONF_ZONE_IS_FALLBACK,
                    default=DEFAULT_ZONE_IS_FALLBACK,
                ): bool,
                vol.Required(
                    CONF_ZONE_PRIORITY,
                    default=DEFAULT_ZONE_PRIORITY,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="add_zone",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Edit an existing climate zone.

        Args:
            user_input: Updated zone configuration

        Returns:
            FlowResult: Show form or update zone
        """
        errors: dict[str, str] = {}

        # If no zone is selected yet, show zone selector
        if self._selected_zone_id is None and user_input is None:
            try:
                redis_client = self._get_redis_client()
                await redis_client.connect()
                zone_ids = await redis_client.get_zone_ids()

                # Get zone data for each zone
                zones = {}
                for zone_id in zone_ids:
                    zone_data = await redis_client.get_zone_state(zone_id)
                    if zone_data:
                        zones[zone_id] = zone_data

                await redis_client.disconnect()

                if not zones:
                    return self.async_abort(reason="no_zones")

                # Store zones for next step
                self._zones = zones

                # Show zone selector
                zone_options = {
                    zone_id: zone_data.get("name", zone_id)
                    for zone_id, zone_data in zones.items()
                }
                data_schema = vol.Schema(
                    {
                        vol.Required("zone_id"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(value=k, label=v)
                                    for k, v in zone_options.items()
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            ),
                        ),
                    }
                )

                return self.async_show_form(
                    step_id="edit_zone",
                    data_schema=data_schema,
                    errors=errors,
                )

            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to load zones: %s", err)
                return self.async_abort(reason="load_zones_failed")

        # Zone selected but no edit input yet
        if user_input is not None and "zone_id" in user_input:
            self._selected_zone_id = user_input["zone_id"]
            zone_data = self._zones[self._selected_zone_id]

            # Show edit form with current values
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_ZONE_NAME,
                        default=zone_data.get("name", ""),
                    ): str,
                    vol.Required(
                        CONF_ZONE_TEMP_SENSOR,
                        default=zone_data.get("temperature_sensor_entity_id", ""),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Required(
                        CONF_ZONE_VALVE_SWITCH,
                        default=zone_data.get("valve_switch_entity_id", ""),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch"),
                    ),
                    vol.Required(
                        CONF_ZONE_TARGET_THRESHOLD,
                        default=zone_data.get(
                            "target_change_threshold", DEFAULT_ZONE_TARGET_THRESHOLD
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=1.0,
                            step=0.1,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(
                        CONF_ZONE_OPENING_OFFSET,
                        default=zone_data.get(
                            "opening_offset", DEFAULT_ZONE_OPENING_OFFSET
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=2.0,
                            step=0.1,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(
                        CONF_ZONE_CLOSING_OFFSET,
                        default=zone_data.get(
                            "closing_offset", DEFAULT_ZONE_CLOSING_OFFSET
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=2.0,
                            step=0.1,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(
                        CONF_ZONE_IS_FALLBACK,
                        default=zone_data.get(
                            "is_fallback_valve", DEFAULT_ZONE_IS_FALLBACK
                        ),
                    ): bool,
                    vol.Required(
                        CONF_ZONE_PRIORITY,
                        default=zone_data.get("priority", DEFAULT_ZONE_PRIORITY),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            )

            return self.async_show_form(
                step_id="edit_zone",
                data_schema=data_schema,
                errors=errors,
            )

        # Process zone update
        if user_input is not None and self._selected_zone_id:
            # Validate entities
            temp_sensor = user_input[CONF_ZONE_TEMP_SENSOR]
            valve_switch = user_input[CONF_ZONE_VALVE_SWITCH]

            registry = er.async_get(self.hass)
            temp_entity = registry.async_get(temp_sensor)
            valve_entity = registry.async_get(valve_switch)

            if temp_entity is None:
                errors["base"] = "invalid_temp_sensor"
            elif valve_entity is None:
                errors["base"] = "invalid_valve_switch"
            else:
                # Update zone
                try:
                    redis_client = self._get_redis_client()
                    await redis_client.connect()

                    zone_data = self._zones[self._selected_zone_id]
                    zone_data.update(
                        {
                            "name": user_input[CONF_ZONE_NAME],
                            "temperature_sensor_entity_id": temp_sensor,
                            "valve_switch_entity_id": valve_switch,
                            "target_change_threshold": user_input[
                                CONF_ZONE_TARGET_THRESHOLD
                            ],
                            "opening_offset": user_input[CONF_ZONE_OPENING_OFFSET],
                            "closing_offset": user_input[CONF_ZONE_CLOSING_OFFSET],
                            "is_fallback_valve": user_input[CONF_ZONE_IS_FALLBACK],
                            "priority": user_input[CONF_ZONE_PRIORITY],
                        }
                    )

                    await redis_client.set_zone_state(self._selected_zone_id, zone_data)
                    await redis_client.disconnect()

                    # Reset selected zone
                    self._selected_zone_id = None
                    self._zones = {}

                    return self.async_create_entry(title="", data={})

                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Failed to update zone: %s", err)
                    errors["base"] = "update_zone_failed"

        return self.async_show_form(step_id="edit_zone", errors=errors)

    async def async_step_delete_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Delete a climate zone.

        Args:
            user_input: Zone to delete

        Returns:
            FlowResult: Confirm and delete zone
        """
        errors: dict[str, str] = {}

        # If no zone is selected yet, show zone selector
        if self._selected_zone_id is None and user_input is None:
            try:
                redis_client = self._get_redis_client()
                await redis_client.connect()
                zone_ids = await redis_client.get_zone_ids()

                # Get zone data for each zone
                zones = {}
                for zone_id in zone_ids:
                    zone_data = await redis_client.get_zone_state(zone_id)
                    if zone_data:
                        zones[zone_id] = zone_data

                await redis_client.disconnect()

                if not zones:
                    return self.async_abort(reason="no_zones")

                # Store zones for next step
                self._zones = zones

                # Show zone selector
                zone_options = {
                    zone_id: zone_data.get("name", zone_id)
                    for zone_id, zone_data in zones.items()
                }
                data_schema = vol.Schema(
                    {
                        vol.Required("zone_id"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(value=k, label=v)
                                    for k, v in zone_options.items()
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            ),
                        ),
                    }
                )

                return self.async_show_form(
                    step_id="delete_zone",
                    data_schema=data_schema,
                    errors=errors,
                )

            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to load zones: %s", err)
                return self.async_abort(reason="load_zones_failed")

        # Zone selected, show confirmation
        if user_input is not None and "zone_id" in user_input:
            self._selected_zone_id = user_input["zone_id"]
            zone_data = self._zones[self._selected_zone_id]

            # Show confirmation
            data_schema = vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                }
            )

            return self.async_show_form(
                step_id="delete_zone",
                data_schema=data_schema,
                description_placeholders={
                    "zone_name": zone_data.get("name", self._selected_zone_id)
                },
                errors=errors,
            )

        # Process deletion
        if user_input is not None and "confirm" in user_input:
            if user_input["confirm"]:
                # Delete zone
                try:
                    redis_client = self._get_redis_client()
                    await redis_client.connect()
                    await redis_client.remove_zone(self._selected_zone_id)
                    await redis_client.disconnect()

                    # Reset selected zone
                    self._selected_zone_id = None
                    self._zones = {}

                    return self.async_create_entry(title="", data={})

                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.exception("Failed to delete zone: %s", err)
                    errors["base"] = "delete_zone_failed"
            else:
                # User cancelled
                self._selected_zone_id = None
                self._zones = {}
                return self.async_abort(reason="deletion_cancelled")

        return self.async_show_form(step_id="delete_zone", errors=errors)

    def _get_redis_client(self) -> RedisClient:
        """
        Get Redis client from config entry.

        Returns:
            RedisClient: Initialized Redis client
        """
        config = self.config_entry.data
        return RedisClient(
            host=config[CONF_REDIS_HOST],
            port=config[CONF_REDIS_PORT],
            password=config.get(CONF_REDIS_PASSWORD),
            db=config[CONF_REDIS_DB],
            key_prefix=config[CONF_REDIS_KEY_PREFIX],
        )
