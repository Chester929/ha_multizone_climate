"""The Multizone Climate integration."""

from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MultizoneClimateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multizone Climate from a config entry."""
    # Get backend port from environment variable (set by addon)
    backend_port = int(os.environ.get("BACKEND_PORT", "8080"))
    backend_url = f"http://localhost:{backend_port}"

    # Create coordinator
    coordinator = MultizoneClimateCoordinator(hass, backend_url)

    # Store coordinator and config in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": entry.data,
    }

    # Start coordinator
    await coordinator.async_config_entry_first_refresh()

    # Forward to climate platform to create zone entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Cleanup coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_shutdown()

        # Remove data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
