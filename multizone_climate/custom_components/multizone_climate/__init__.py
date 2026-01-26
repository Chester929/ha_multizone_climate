"""The Multizone Climate integration."""

from __future__ import annotations

import logging
import os
import uuid

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MultizoneClimateCoordinator
from .core import RedisClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multizone Climate from a config entry."""
    # Get backend port from environment variable (set by addon)
    backend_port = int(os.environ.get("BACKEND_PORT", "8080"))
    backend_url = f"http://localhost:{backend_port}"

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
    coordinator = MultizoneClimateCoordinator(hass, backend_url)

    # Store coordinator, redis_client and config in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "redis_client": redis_client,  # TODO: Remove when platforms use API
        "config": entry.data,
    }

    # Start coordinator
    await coordinator.async_config_entry_first_refresh()

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
            zone_data = {
                "id": zone_id,
                "name": entry.data.get("zone_name", "Fallback Zone"),
                "temperature_sensor_entity_id": entry.data.get("temperature_sensor"),
                "valve_switch_entity_id": entry.data.get("valve_switch"),
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

                # Also register zone with backend via API
                zone_config = {
                    "id": zone_id,  # Backend expects 'id', not 'zone_id'
                    "name": zone_data["name"],
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
                            if response.status not in (200, 201):
                                _LOGGER.warning(
                                    f"Failed to register initial zone {zone_id} with backend: status {response.status}"
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

    # Forward to climate platform to create zone entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Cleanup coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_shutdown()

        # Cleanup redis client
        redis_client = hass.data[DOMAIN][entry.entry_id]["redis_client"]
        await redis_client.disconnect()

        # Remove data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
