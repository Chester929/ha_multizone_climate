"""Config flow for Multizone Climate integration."""

from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("main_climate_entity"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN),
        ),
    }
)


class MultizoneClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multizone Climate."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step - Main Climate Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate configurations
            for entry in self._async_current_entries():
                if entry.data.get("main_climate_entity") == user_input.get(
                    "main_climate_entity"
                ):
                    errors["base"] = "already_configured"
                    break

            if not errors:
                # Validate the main climate entity exists
                if not self.hass.states.get(user_input["main_climate_entity"]):
                    errors["main_climate_entity"] = "entity_not_found"
                else:
                    # Store main climate entity and proceed to zone setup
                    self.data = user_input
                    return await self.async_step_zones()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "description": "Configure the main climate entity that controls your HVAC system."
            },
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle zone configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate temperature_sensor entity exists
            if not self.hass.states.get(user_input["temperature_sensor"]):
                errors["temperature_sensor"] = "entity_not_found"

            # Validate valve_switch entity exists
            if not self.hass.states.get(user_input["valve_switch"]):
                errors["valve_switch"] = "entity_not_found"

            if not errors:
                # Merge zone data with main climate data
                self.data.update(user_input)

                # Create the config entry
                return self.async_create_entry(
                    title=f"Multizone Climate ({user_input.get('zone_name', 'Zone 1')})",
                    data=self.data,
                )

        # Schema for zone configuration with entity selectors
        zones_schema = vol.Schema(
            {
                vol.Required("zone_name", default="Zone 1"): cv.string,
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=SENSOR_DOMAIN,
                        device_class="temperature",
                    ),
                ),
                vol.Required("valve_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[SWITCH_DOMAIN, "valve"]),
                ),
                vol.Optional(
                    "target_temperature", default=20.0
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5.0,
                        max=35.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional("priority", default=50): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="zones",
            data_schema=zones_schema,
            errors=errors,
            description_placeholders={
                "description": "Configure a heating/cooling zone with temperature sensor and valve control."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MultizoneClimateOptionsFlow:
        """Get the options flow for this handler."""
        return MultizoneClimateOptionsFlow(config_entry)


class MultizoneClimateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Multizone Climate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Merge user input with existing config data
            new_data = {**self.config_entry.data, **user_input}
            
            # Update the config entry data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            
            # Update the backend zone via API if we have a zone_id
            zone_id = self.config_entry.entry_id
            backend_port = int(os.environ.get("BACKEND_PORT", "8080"))
            backend_url = f"http://localhost:{backend_port}"
            
            # Prepare zone update payload
            zone_update = {
                "name": user_input.get("zone_name"),
                "target_temperature": user_input.get("target_temperature"),
                "priority": user_input.get("priority"),
                "opening_offset": user_input.get("opening_offset"),
                "closing_offset": user_input.get("closing_offset"),
                "target_change_threshold": user_input.get("target_change_threshold"),
                "is_fallback_valve": user_input.get("is_fallback_valve"),
                "temperature_sensor_entity_id": user_input.get("temperature_sensor"),
                "valve_switch_entity_id": user_input.get("valve_switch"),
            }
            
            # Remove None values
            zone_update = {k: v for k, v in zone_update.items() if v is not None}
            
            # Update zone via backend API
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        f"{backend_url}/api/zones/{zone_id}",
                        json=zone_update,
                    ) as response:
                        if response.status not in (200, 201):
                            _LOGGER.warning(
                                f"Failed to update zone {zone_id} via backend API: status {response.status}"
                            )
            except Exception as err:
                _LOGGER.error(f"Error updating zone {zone_id} via backend API: {err}")
            
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "main_climate_entity",
                    default=self.config_entry.data.get("main_climate_entity"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN),
                ),
                vol.Optional(
                    "zone_name",
                    default=self.config_entry.data.get("zone_name", "Zone 1"),
                ): cv.string,
                vol.Optional(
                    "temperature_sensor",
                    default=self.config_entry.data.get("temperature_sensor"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=SENSOR_DOMAIN,
                        device_class="temperature",
                    ),
                ),
                vol.Optional(
                    "valve_switch",
                    default=self.config_entry.data.get("valve_switch"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[SWITCH_DOMAIN, "valve"]),
                ),
                vol.Optional(
                    "target_temperature", 
                    default=self.config_entry.data.get("target_temperature", 20.0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5.0,
                        max=35.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    "priority", 
                    default=self.config_entry.data.get("priority", 50)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                # Note: 0.3 is the canonical default for `opening_offset`, aligned with the
                # Go backend. For existing entries that already have an `opening_offset`
                # stored (e.g. legacy setups that used 0.5 in the old Python code),
                # we intentionally preserve the stored value via `config_entry.data`.
                vol.Optional(
                    "opening_offset",
                    default=self.config_entry.data.get("opening_offset", 0.3)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    "closing_offset",
                    # Note: Existing config entries created with the legacy Python implementation
                    # may have a stored default of 0.5 for `closing_offset`. We intentionally
                    # reuse the stored value here (when present) for backward compatibility,
                    # while falling back to 0.3 to match the Go backend's default for new zones.
                    default=self.config_entry.data.get("closing_offset", 0.3)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    "target_change_threshold",
                    default=self.config_entry.data.get("target_change_threshold", 0.1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    "is_fallback_valve",
                    default=self.config_entry.data.get("is_fallback_valve", False)
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
