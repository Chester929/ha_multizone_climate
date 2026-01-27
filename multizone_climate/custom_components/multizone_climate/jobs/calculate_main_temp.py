"""Calculate main target temperature job."""

from __future__ import annotations

from typing import Any
import logging

from .base import BaseJob
from ..core.algorithms import calculate_main_target_temperature

_LOGGER = logging.getLogger(__name__)


class CalculateMainTempJob(BaseJob):
    """
    Background job to calculate and update main climate target temperature.

    Triggered when:
    - Zone target temperature changes
    - Zone current temperature changes significantly
    - Zone state changes (ON/OFF)
    """

    def __init__(self, redis_client: Any, hass: Any) -> None:
        """
        Initialize calculate main temp job.

        Args:
            redis_client: Redis client for data access
            hass: Home Assistant instance
        """
        super().__init__("calculate_main_temp", redis_client, hass)

    async def _execute_impl(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute main target temperature calculation.

        Args:
            job_data: Job parameters:
                - trigger: What triggered this calculation
                - changed_zones: List of zone IDs that changed

        Returns:
            dict: Result with:
                - main_target_calculated: New main target temperature
                - main_target_updated: Whether main climate was updated
                - zones_processed: Number of zones considered

        Steps:
            1. Fetch global config from Redis
            2. Fetch all zone states from Redis
            3. Get current main climate target
            4. Call calculate_main_target_temperature()
            5. If result is not None, update main climate entity
            6. Return result
        """
        _LOGGER.debug("Starting calculate main temp job: %s", job_data)

        # Fetch config from Redis
        config = await self.redis_client.get_config()
        if not config:
            _LOGGER.warning("No config found in Redis")
            return {"error": "no_config"}

        # Check if multizone is enabled
        multizone_enabled = config.get("multizone_enabled", False)
        if not multizone_enabled:
            _LOGGER.debug(
                "Multizone disabled, skipping main target calculation. "
                "Zones control valves individually."
            )
            return {
                "main_target_calculated": None,
                "main_target_updated": False,
                "zones_processed": 0,
                "skipped_reason": "multizone_disabled",
            }

        # Fetch all zone states
        zone_states = await self._fetch_zone_states()
        if not zone_states:
            _LOGGER.debug("No zones found")
            return {
                "main_target_calculated": None,
                "main_target_updated": False,
                "zones_processed": 0,
            }

        # Get current main climate state
        main_climate = await self.redis_client.get_main_climate_state()
        current_main_target = main_climate.get("target_temperature", 20.0)
        # Use None when current temperature is unavailable; algorithms.py treats None as zero capability
        main_current_temp = main_climate.get("current_temperature")

        if main_current_temp is None:
            _LOGGER.warning(
                "Main climate current temperature not available in Redis, "
                "assuming zero heating capability for boost calculation"
            )

        # Call calculate_main_target_temperature()
        new_target = calculate_main_target_temperature(
            zones=zone_states,
            config=config,
            current_main_target=current_main_target,
            main_current_temp=main_current_temp,
        )

        # If new target returned, update main climate entity
        updated = False
        if new_target is not None:
            await self._update_main_climate_target(new_target)
            updated = True
            _LOGGER.info(
                "Main target updated: %.1f°C -> %.1f°C (%d zones)",
                current_main_target,
                new_target,
                len(zone_states),
            )
        else:
            _LOGGER.debug(
                "Main target unchanged: %.1f°C (change below threshold)",
                current_main_target,
            )

        return {
            "main_target_calculated": new_target,
            "main_target_updated": updated,
            "zones_processed": len(zone_states),
            "current_main_target": current_main_target,
        }

    async def _fetch_zone_states(self) -> list[dict[str, Any]]:
        """
        Fetch all zone states from Redis.

        Returns:
            list: List of zone state dicts
        """
        zone_ids = await self.redis_client.get_zone_ids()
        zone_states = []

        for zone_id in zone_ids:
            state = await self.redis_client.get_zone_state(zone_id)
            if state:
                state["id"] = zone_id
                zone_states.append(state)

        return zone_states

    async def _update_main_climate_target(self, new_target: float) -> None:
        """
        Update main climate entity target temperature.

        Args:
            new_target: New target temperature to set

        Tasks:
            - Call climate.set_temperature service
            - Update main_climate state in Redis
        """
        # Get main climate entity ID from config
        config = await self.redis_client.get_config()
        main_climate_entity_id = config.get("main_climate_entity_id")

        if not main_climate_entity_id:
            _LOGGER.error("No main climate entity ID in config")
            return

        # Call hass.services.async_call("climate", "set_temperature", ...)
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": main_climate_entity_id,
                    "temperature": new_target,
                },
                blocking=True,
            )
            _LOGGER.debug(
                "Set main climate %s to %.1f°C",
                main_climate_entity_id,
                new_target,
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to set main climate target: %s",
                err,
                exc_info=True,
            )
            raise

        # Update Redis main_climate state
        main_climate_state = await self.redis_client.get_main_climate_state()
        main_climate_state["target_temperature"] = new_target
        await self.redis_client.set_main_climate_state(main_climate_state)
