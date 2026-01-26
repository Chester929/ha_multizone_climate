"""The Multizone Climate integration."""

from __future__ import annotations

import logging
import os

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
