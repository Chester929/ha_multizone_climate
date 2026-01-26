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
                    return await self.async_step_zone_initial()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "description": "Configure the main climate entity that controls your HVAC system. At least one fallback zone is required."
            },
        )

    async def async_step_zone_initial(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle initial zone configuration step (required fallback zone)."""
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
                    title="Multizone Climate",
                    data=self.data,
                )

        # Schema for initial fallback zone configuration
        zone_schema = vol.Schema(
            {
                vol.Required("zone_name", default="Fallback Zone"): cv.string,
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
                vol.Optional(
                    "opening_offset",
                    default=0.3
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
                    default=0.3
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
                    default=0.1
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                # This first zone must be a fallback valve (fixed to True)
                vol.Required(
                    "is_fallback_valve",
                    default=True
                ): vol.All(cv.boolean, vol.In([True])),
            }
        )

        return self.async_show_form(
            step_id="zone_initial",
            data_schema=zone_schema,
            errors=errors,
            description_placeholders={
                "description": "Configure the first fallback zone. This zone is required and must be set as a fallback valve to ensure at least one valve can be opened when the minimum valve requirement is active."
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
        self.zone_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options - show menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_zone":
                return await self.async_step_add_zone()
            elif action == "edit_main":
                return await self.async_step_edit_main()

        # Show menu with options
        menu_schema = vol.Schema(
            {
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "add_zone", "label": "Add New Zone"},
                            {"value": "edit_main", "label": "Edit Main Climate Entity"},
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=menu_schema,
        )

    async def async_step_edit_main(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Edit main climate entity configuration."""
        if user_input is not None:
            # Validate the main climate entity exists
            if not self.hass.states.get(user_input["main_climate_entity"]):
                return self.async_show_form(
                    step_id="edit_main",
                    data_schema=self._get_edit_main_schema(),
                    errors={"main_climate_entity": "entity_not_found"},
                )

            # Update the config entry data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )

            # Reload the config entry so the integration uses the updated main climate entity
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_main",
            data_schema=self._get_edit_main_schema(),
        )

    def _get_edit_main_schema(self) -> vol.Schema:
        """Get schema for editing main climate entity."""
        return vol.Schema(
            {
                vol.Required(
                    "main_climate_entity",
                    default=self.config_entry.data.get("main_climate_entity"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN),
                ),
            }
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Add a new zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate temperature_sensor entity exists
            if not self.hass.states.get(user_input["temperature_sensor"]):
                errors["temperature_sensor"] = "entity_not_found"

            # Validate valve_switch entity exists
            if not self.hass.states.get(user_input["valve_switch"]):
                errors["valve_switch"] = "entity_not_found"

            if not errors:
                # Generate a unique zone_id
                import uuid
                zone_id = str(uuid.uuid4())

                # Get Redis client from hass.data
                data = self.hass.data[DOMAIN][self.config_entry.entry_id]
                redis_client = data["redis_client"]

                # Prepare zone data for Redis
                zone_data = {
                    "id": zone_id,
                    "name": user_input.get("zone_name", "Zone"),
                    "temperature_sensor_entity_id": user_input.get("temperature_sensor"),
                    "valve_switch_entity_id": user_input.get("valve_switch"),
                    "target_temperature": user_input.get("target_temperature", 20.0),
                    "priority": user_input.get("priority", 50),
                    "opening_offset": user_input.get("opening_offset", 0.3),
                    "closing_offset": user_input.get("closing_offset", 0.3),
                    "target_change_threshold": user_input.get("target_change_threshold", 0.1),
                    "is_fallback_valve": user_input.get("is_fallback_valve", False),
                    "current_temperature": 0.0,
                    "satisfaction": "unknown",
                    "valve_state": "unknown",
                    "temperature_rising": False,
                    "temperature_falling": False,
                }

                # Add zone to Redis
                try:
                    await redis_client.add_zone(zone_id, zone_data)
                    _LOGGER.info(f"Added zone {zone_id} ({zone_data['name']}) to Redis")

                    # Also register zone with backend via API
                    backend_port = int(os.environ.get("BACKEND_PORT", "8080"))
                    backend_url = f"http://localhost:{backend_port}"

                    zone_config = {
                        "zone_id": zone_id,
                        "name": zone_data["name"],
                        "temperature_sensor_entity_id": zone_data["temperature_sensor_entity_id"],
                        "valve_switch_entity_id": zone_data["valve_switch_entity_id"],
                        "target_temperature": zone_data["target_temperature"],
                        "opening_offset": zone_data["opening_offset"],
                        "closing_offset": zone_data["closing_offset"],
                        "priority": zone_data["priority"],
                        "is_fallback_valve": zone_data["is_fallback_valve"],
                    }

                    try:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                f"{backend_url}/api/zones",
                                json=zone_config,
                            ) as response:
                                if response.status not in (200, 201):
                                    _LOGGER.warning(
                                        f"Failed to register zone {zone_id} with backend: status {response.status}"
                                    )
                    except Exception as err:
                        _LOGGER.error(f"Error registering zone {zone_id} with backend: {err}")

                except Exception as err:
                    _LOGGER.error(f"Failed to add zone to Redis: {err}")
                    errors["base"] = "redis_error"
                    return self.async_show_form(
                        step_id="add_zone",
                        data_schema=self._get_add_zone_schema(),
                        errors=errors,
                    )

                # Reload the integration to pick up the new zone
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_zone",
            data_schema=self._get_add_zone_schema(),
            errors=errors,
            description_placeholders={
                "description": "Configure a new heating/cooling zone with temperature sensor and valve control."
            },
        )

    def _get_add_zone_schema(self) -> vol.Schema:
        """Get schema for adding a new zone."""
        return vol.Schema(
            {
                vol.Required("zone_name", default="Zone"): cv.string,
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
                vol.Optional(
                    "opening_offset",
                    default=0.3
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
                    default=0.3
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
                    default=0.1
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
                    default=False
                ): cv.boolean,
            }
        )
