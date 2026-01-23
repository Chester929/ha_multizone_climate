"""Switch platform for Multizone Climate integration."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.switch import SwitchEntity  # type: ignore[import-not-found]
from homeassistant.config_entries import ConfigEntry  # type: ignore[import-not-found]
from homeassistant.core import HomeAssistant, callback  # type: ignore[import-not-found]
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore[import-not-found]

from ..const import DOMAIN, JOB_TYPE_CALCULATE_MAIN_TEMP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up switch entities.

    Creates switches for:
    - Multizone feature enable/disable
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    redis_client = data["redis_client"]

    # Create multizone enable switch
    multizone_switch = MultizoneEnableSwitch(coordinator, redis_client)

    async_add_entities([multizone_switch])


class MultizoneEnableSwitch(SwitchEntity):
    """Switch to enable/disable multizone feature."""

    def __init__(self, coordinator: Any, redis_client: Any) -> None:
        """
        Initialize multizone enable switch.

        Args:
            coordinator: Data update coordinator
            redis_client: Redis client
        """
        self.coordinator = coordinator
        self.redis_client = redis_client
        self._attr_unique_id = f"{DOMAIN}_multizone_enabled"
        self._attr_name = "Multizone Enabled"
        self._attr_should_poll = False

    @property
    def device_info(self) -> dict:
        """Return device information for grouping entities."""
        return {
            "identifiers": {(DOMAIN, "multizone_climate_main")},
            "name": "Multizone Climate",
            "manufacturer": "Chester929",
            "model": "Multizone Climate Controller",
        }

    @property
    def is_on(self) -> bool:
        """
        Return True if multizone is enabled.

        Returns:
            bool: Current enable state
        """
        config = self.coordinator.get_config()
        if not config:
            return False
        return bool(config.get("multizone_enabled", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """
        Enable multizone feature.

        Requirements:
        - At least one zone must be turned ON
        """
        # Check if at least one zone is ON
        zones = self.coordinator.data.get("zones", {}) if self.coordinator.data else {}
        has_on_zone = any(zone.get("is_on", False) for zone in zones.values())

        if not has_on_zone:
            _LOGGER.warning("Cannot enable multizone: no zones are turned ON")
            return

        try:
            # Update config in Redis
            config = self.coordinator.get_config() or {}
            config["multizone_enabled"] = True
            await self.redis_client.set_config(config)

            # Trigger coordinator update and recalculation
            await self.coordinator.async_request_refresh()
            await self.redis_client.enqueue_job(
                JOB_TYPE_CALCULATE_MAIN_TEMP,
                {
                    "job_id": f"enable_multizone_{int(self.coordinator.hass.loop.time())}",
                    "trigger": "multizone_enabled",
                    "enqueued_at": self.coordinator.hass.loop.time(),
                },
            )
        except Exception as err:
            _LOGGER.error("Failed to enable multizone: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """
        Disable multizone feature.

        Each zone will manage its own valve independently.
        """
        try:
            # Update config in Redis
            config = self.coordinator.get_config() or {}
            config["multizone_enabled"] = False
            await self.redis_client.set_config(config)

            # Trigger coordinator update
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable multizone: %s", err)
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
