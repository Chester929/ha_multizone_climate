"""Config flow for Multizone Climate integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

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
)

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multizone Climate."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - Redis configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # TODO: Test Redis connection
            # Store Redis config and move to next step
            self._redis_config = user_input
            return await self.async_step_main_climate()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_REDIS_HOST, default=DEFAULT_REDIS_HOST
                ): cv.string,
                vol.Required(
                    CONF_REDIS_PORT, default=DEFAULT_REDIS_PORT
                ): cv.port,
                vol.Optional(CONF_REDIS_PASSWORD): cv.string,
                vol.Required(
                    CONF_REDIS_DB, default=DEFAULT_REDIS_DB
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=15)),
                vol.Required(
                    CONF_REDIS_KEY_PREFIX, default=DEFAULT_REDIS_KEY_PREFIX
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_main_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure main climate entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine Redis config with main climate config
            config_data = {**self._redis_config, **user_input}
            
            # Create the config entry
            return self.async_create_entry(
                title="Multizone Climate",
                data=config_data,
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAIN_CLIMATE_ENTITY): cv.entity_id,
                vol.Required(
                    CONF_USE_AVERAGE_MODE, default=DEFAULT_USE_AVERAGE_MODE
                ): cv.boolean,
                vol.Required(
                    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    default=DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                vol.Required(
                    CONF_MIN_VALVES_OPEN, default=DEFAULT_MIN_VALVES_OPEN
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_MAIN_MIN_TEMP, default=DEFAULT_MAIN_MIN_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=35.0)),
                vol.Required(
                    CONF_MAIN_MAX_TEMP, default=DEFAULT_MAIN_MAX_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=35.0)),
                vol.Required(
                    CONF_MAIN_CHANGE_THRESHOLD, default=DEFAULT_MAIN_CHANGE_THRESHOLD
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
                vol.Required(
                    CONF_VALVE_ACTUATION_DELAY, default=DEFAULT_VALVE_ACTUATION_DELAY
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
                vol.Required(
                    CONF_COORDINATOR_INTERVAL, default=DEFAULT_COORDINATOR_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Required(
                    CONF_SATISFACTION_EPS, default=DEFAULT_SATISFACTION_EPS
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            }
        )

        return self.async_show_form(
            step_id="main_climate", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MultizoneClimateOptionsFlow(config_entry)


class MultizoneClimateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Multizone Climate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build options schema with current values
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    default=self.config_entry.data.get(
                        CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                        DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                vol.Required(
                    CONF_USE_AVERAGE_MODE,
                    default=self.config_entry.data.get(
                        CONF_USE_AVERAGE_MODE, DEFAULT_USE_AVERAGE_MODE
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_MIN_VALVES_OPEN,
                    default=self.config_entry.data.get(
                        CONF_MIN_VALVES_OPEN, DEFAULT_MIN_VALVES_OPEN
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
