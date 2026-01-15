"""Switch platform for Multizone Climate integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Multizone Climate switch platform."""
    _LOGGER.info("Setting up switch entities")
    
    # TODO: Create multizone enable/disable switch
    
    async_add_entities([])


class MultizoneEnableSwitch(SwitchEntity):
    """Switch to enable/disable multizone feature."""
    
    def __init__(self) -> None:
        """Initialize the multizone enable switch."""
        # TODO: Implement multizone enable/disable switch
        pass
