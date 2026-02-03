"""The Multizone Climate integration."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import cast

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MultizoneClimateCoordinator
from .core import RedisClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multizone Climate from a config entry."""
    # Get backend port from environment variable (set by addon)
    backend_port = int(os.environ.get("BACKEND_PORT", "8080"))
    backend_url = f"http://localhost:{backend_port}"

    # Get coordinator interval from environment variable (set by addon)
    raw_coordinator_interval = os.environ.get("COORDINATOR_INTERVAL", "30")
    try:
        coordinator_interval = int(raw_coordinator_interval)
        # Ensure the value is positive
        if coordinator_interval <= 0:
            raise ValueError("Coordinator interval must be positive")
    except ValueError:
        _LOGGER.warning(
            "Invalid COORDINATOR_INTERVAL value '%s'; falling back to default 30 seconds",
            raw_coordinator_interval
        )
        coordinator_interval = 30

    # Get Redis configuration from environment variables
    # NOTE: Redis client is used by platform code but should be replaced
    # with backend API calls in future refactoring
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    redis_password = os.environ.get("REDIS_PASSWORD")

    # Create and connect Redis client
    redis_client = RedisClient(
        host=redis_host,
        port=redis_port,
        password=redis_password,
    )
    await redis_client.connect()

    # Create coordinator that communicates with backend API
    coordinator = MultizoneClimateCoordinator(hass, backend_url, redis_client)

    # Store coordinator, redis_client and config in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "redis_client": redis_client,  # TODO: Remove when platforms use API
        "config": entry.data,
    }

    # Start coordinator
    await coordinator.async_config_entry_first_refresh()

    # Initialize global config if it doesn't exist
    existing_config = await redis_client.get_config()
    if not existing_config:
        # Create initial config with default values
        initial_config = {
            "main_climate_entity_id": entry.data.get("main_climate_entity", ""),
            "main_target_all_zones_satisfied": 0.5,
            "use_average_mode": False,
            "min_valves_open": 1,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
            "valve_actuation_delay": 120,
            "coordinator_interval": coordinator_interval,
            "satisfaction_eps": 0.0,
            "multizone_enabled": False,
        }

        # Add outdoor temperature sensor if provided
        outdoor_sensor = entry.data.get("outdoor_temperature_sensor")
        if outdoor_sensor:
            initial_config["outdoor_temperature_sensor"] = outdoor_sensor

        await redis_client.set_config(initial_config)
        _LOGGER.info(
            f"Initialized global config in Redis with main_climate_entity_id={initial_config['main_climate_entity_id']}"
        )
    else:
        _LOGGER.info(
            f"Global config already exists in Redis (found {len(existing_config)} keys), skipping initialization"
        )

    # Initialize main climate state if it doesn't exist
    existing_main_climate = await redis_client.get_main_climate_state()
    if not existing_main_climate:
        # Get initial state from main climate entity
        main_climate_entity_id = entry.data.get("main_climate_entity", "")
        main_climate_state_obj = hass.states.get(main_climate_entity_id) if main_climate_entity_id else None

        # Retry once if entity is not available (entity might be initializing)
        if not main_climate_state_obj and main_climate_entity_id:
            _LOGGER.info(
                f"Main climate entity {main_climate_entity_id} not available, waiting 1 second and retrying..."
            )
            await asyncio.sleep(1)
            main_climate_state_obj = hass.states.get(main_climate_entity_id)

        # Initialize with actual data from HA entity if available
        if main_climate_state_obj:
            attrs = main_climate_state_obj.attributes

            # Create initial main climate state with actual data from HA entity
            initial_main_climate = {
                "entity_id": main_climate_entity_id,
                "current_temperature": attrs.get("current_temperature", 0.0),
                "target_temperature": attrs.get("temperature", 22.0),
                "outdoor_temperature": 0.0,  # Will be populated from sensor below if available
                "hvac_mode": main_climate_state_obj.state,
                "hvac_action": attrs.get("hvac_action", "idle"),
            }

            # Get outdoor temperature from sensor if provided
            outdoor_sensor = entry.data.get("outdoor_temperature_sensor")
            if outdoor_sensor:
                outdoor_state = hass.states.get(outdoor_sensor)
                if outdoor_state:
                    try:
                        initial_main_climate["outdoor_temperature"] = float(outdoor_state.state)
                    except (ValueError, TypeError):
                        _LOGGER.warning(f"Could not parse outdoor temperature from {outdoor_sensor}, using 0.0")

            await redis_client.set_main_climate_state(initial_main_climate)
            _LOGGER.info(
                f"Initialized main climate state in Redis for {main_climate_entity_id} with actual data from HA"
            )
        else:
            # Entity still not available after retry - use defaults for initialization
            _LOGGER.warning(
                f"Cannot fetch data from main climate entity {main_climate_entity_id} after retry. "
                f"Initializing with default values."
            )

            # Create initial main climate state with default values
            initial_main_climate = {
                "entity_id": main_climate_entity_id,
                "current_temperature": 0.0,
                "target_temperature": 22.0,
                "outdoor_temperature": 0.0,
                "hvac_mode": "unknown",
                "hvac_action": "idle",
            }

            await redis_client.set_main_climate_state(initial_main_climate)
            _LOGGER.info(
                f"Initialized main climate state in Redis for {main_climate_entity_id} with default values"
            )
    else:
        _LOGGER.info(
            f"Main climate state already exists in Redis (found {len(existing_main_climate)} keys), skipping initialization"
        )

    # Check if this is initial setup with zone data in entry.data
    # Only create initial zone if Redis is empty (prevents duplicates on restart)
    required_zone_fields = ["zone_name", "temperature_sensor", "valve_switch"]
    has_initial_zone = all(field in entry.data for field in required_zone_fields)

    if has_initial_zone:
        # Check if zones already exist in Redis to prevent duplicates
        existing_zones = await redis_client.get_zone_ids()

        if not existing_zones:
            # No zones in Redis, create the initial fallback zone
            zone_id = str(uuid.uuid4())

            # Prepare zone data for Redis
            valve_switch_entity_id = entry.data.get("valve_switch")
            zone_data = {
                "id": zone_id,
                "name": entry.data.get("zone_name", "Fallback Zone"),
                "enabled": "true",
                "temperature_sensor_entity_id": entry.data.get("temperature_sensor"),
                "valve_switch_entity_id": valve_switch_entity_id,
                "valve_id": valve_switch_entity_id,  # Alias for compatibility with valve controller
                "target_temperature": entry.data.get("target_temperature", 20.0),
                "priority": entry.data.get("priority", 50),
                "opening_offset": entry.data.get("opening_offset", 0.3),
                "closing_offset": entry.data.get("closing_offset", 0.3),
                "target_change_threshold": entry.data.get(
                    "target_change_threshold", 0.1
                ),
                "is_fallback_valve": entry.data.get("is_fallback_valve", True),
                "current_temperature": 0.0,
                "satisfaction": "unknown",
                "valve_state": "unknown",
                "temperature_rising": False,
                "temperature_falling": False,
            }

            # Add zone to Redis
            try:
                await redis_client.add_zone(zone_id, zone_data)
                _LOGGER.info(
                    f"Added initial fallback zone {zone_id} ({zone_data['name']}) to Redis"
                )

                # Get actual valve state from Home Assistant and update Redis
                valve_switch_entity_id = zone_data["valve_switch_entity_id"]
                if valve_switch_entity_id:
                    try:
                        valve_state_obj = hass.states.get(valve_switch_entity_id)
                        if valve_state_obj:
                            # Map HA state to valve_state (on/off -> opened/closed)
                            actual_valve_state = "opened" if valve_state_obj.state == "on" else "closed"
                            zone_data["valve_state"] = actual_valve_state
                            await redis_client.set_zone_state(zone_id, zone_data)
                            _LOGGER.info(
                                f"Initialized valve state for zone {zone_id}: {actual_valve_state} (from entity {valve_switch_entity_id})"
                            )
                        else:
                            _LOGGER.warning(
                                f"Valve switch entity {valve_switch_entity_id} not found for zone {zone_id}, valve state remains 'unknown'"
                            )
                    except Exception as valve_err:
                        _LOGGER.error(
                            f"Failed to get valve state for zone {zone_id}: {valve_err}"
                        )

                # Also register zone with backend via API
                zone_config = {
                    "id": zone_id,  # Backend expects 'id', not 'zone_id'
                    "name": zone_data["name"],
                    "enabled": "true",
                    "temperature_sensor_entity_id": zone_data[
                        "temperature_sensor_entity_id"
                    ],
                    "valve_switch_entity_id": zone_data["valve_switch_entity_id"],
                    "target_temperature": zone_data["target_temperature"],
                    "opening_offset": zone_data["opening_offset"],
                    "closing_offset": zone_data["closing_offset"],
                    "priority": zone_data["priority"],
                    "is_fallback_valve": zone_data["is_fallback_valve"],
                }

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{backend_url}/api/zones",
                            json=zone_config,
                        ) as response:
                            # 409 Conflict means zone already exists in backend, which is acceptable
                            if response.status not in (200, 201, 409):
                                _LOGGER.warning(
                                    f"Failed to register initial zone {zone_id} with backend: status {response.status}"
                                )
                            elif response.status == 409:
                                _LOGGER.info(
                                    f"Zone {zone_id} already exists in backend (status 409), skipping registration"
                                )
                            else:
                                _LOGGER.info(
                                    f"Successfully registered zone {zone_id} with backend"
                                )
                except Exception as err:
                    _LOGGER.error(
                        f"Error registering initial zone {zone_id} with backend: {err}"
                    )

            except Exception as err:
                _LOGGER.error(f"Failed to add initial zone to Redis: {err}")
        else:
            _LOGGER.info(
                f"Initial zone already exists in Redis (found {len(existing_zones)} zones), skipping creation"
            )

    # Register main device in device registry
    from homeassistant.helpers import device_registry as dr
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "main")},
        name="Multizone Climate",
        manufacturer="Multizone Climate",
        model="Main Controller",
        sw_version="0.1.x-dev",
    )

    # Forward to climate platform to create zone entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start job worker to process background jobs
    await coordinator.start_job_worker()

    # Set up valve state change automation
    from .automations import ValveStateChangeAutomation
    valve_state_automation = ValveStateChangeAutomation(hass, redis_client)
    await valve_state_automation.setup()

    # Store automation in hass.data for cleanup on unload
    hass.data[DOMAIN][entry.entry_id]["valve_state_automation"] = valve_state_automation

    # Register update listener for options flow changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Reload the config entry to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = cast(
        bool, await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    )

    if unload_ok:
        # Stop valve state automation
        valve_state_automation = hass.data[DOMAIN][entry.entry_id].get("valve_state_automation")
        if valve_state_automation:
            await valve_state_automation.stop()

        # Stop job worker first
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.stop_job_worker()

        # Cleanup coordinator
        await coordinator.async_shutdown()

        # Disconnect from Redis but don't clear data (preserve for reload)
        redis_client = hass.data[DOMAIN][entry.entry_id]["redis_client"]
        await redis_client.disconnect()

        # Remove data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry - clear all Redis data."""
    # Get Redis configuration from environment variables
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port_str = os.environ.get("REDIS_PORT", "6379")
    redis_password = os.environ.get("REDIS_PASSWORD")

    # Parse port with error handling
    try:
        redis_port = int(redis_port_str)
    except (ValueError, TypeError):
        _LOGGER.warning(
            f"Invalid REDIS_PORT value '{redis_port_str}', using default 6379"
        )
        redis_port = 6379

    # Create temporary Redis client to clear data
    redis_client = RedisClient(
        host=redis_host,
        port=redis_port,
        password=redis_password,
    )
    await redis_client.connect()

    _LOGGER.debug("Clearing Redis data for integration removal")
    await redis_client.clear_all_data()
    await redis_client.disconnect()
    _LOGGER.info("Cleared all Redis data for removed integration")
