"""Safety valve check background job."""

from __future__ import annotations

from typing import Any
import logging

from .base import BaseJob
from ..core.safety import SafetyChecker

_LOGGER = logging.getLogger(__name__)


class SafetyCheckJob(BaseJob):
    """
    Background job to ensure minimum valves are open.

    Runs periodically (every valve_actuation_delay / 2) to verify
    system safety and force open fallback valves if needed.
    """

    def __init__(self, redis_client: Any, hass: Any) -> None:
        """
        Initialize safety check job.

        Args:
            redis_client: Redis client for data access
            hass: Home Assistant instance
        """
        super().__init__("safety_check", redis_client, hass)
        self.safety_checker: SafetyChecker | None = None

    async def _execute_impl(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute safety check.

        Args:
            job_data: Job parameters (usually empty for timer-triggered job)

        Returns:
            dict: Result with:
                - valves_open_count: Number of currently open valves
                - min_required: Minimum required valves
                - safety_satisfied: True if requirement met
                - fallback_valves_opened: List of fallback valves forced open

        Steps:
            1. Fetch config from Redis
            2. Fetch all zone states from Redis
            3. Call SafetyChecker.check_minimum_valves()
            4. If valves need to be forced open:
               a. Log warning
               b. Open fallback valves
               c. Set valve locks
               d. Update zone states
            5. Return result
        """
        _LOGGER.debug("Starting safety check job: %s", job_data)

        # Fetch config
        config = await self.redis_client.get_config()
        if not config:
            _LOGGER.warning("No config found in Redis")
            return {"error": "no_config"}

        # Initialize safety checker with config
        if not self.safety_checker:
            self.safety_checker = SafetyChecker(self.redis_client, config)

        # Fetch all zone states
        zone_ids = await self.redis_client.get_zone_ids()
        zones = []
        for zone_id in zone_ids:
            state = await self.redis_client.get_zone_state(zone_id)
            if state:
                state["id"] = zone_id
                zones.append(state)

        # Count open valves before check
        valves_open_count = sum(
            1 for zone in zones if zone.get("valve_state") == "open"
        )
        min_required = config.get("min_valves_open", 1)

        # Call safety_checker.check_minimum_valves()
        valves_to_force_open = await self.safety_checker.check_minimum_valves(zones)

        fallback_valves_opened = []

        # If result is not empty, force open valves
        if valves_to_force_open:
            _LOGGER.warning(
                "Safety check: Forcing open %d fallback valves",
                len(valves_to_force_open),
            )

            for valve_id in valves_to_force_open:
                await self._force_open_valve(valve_id)
                fallback_valves_opened.append(valve_id)

        safety_satisfied = (valves_open_count >= min_required) or bool(
            fallback_valves_opened
        )

        _LOGGER.debug(
            "Safety check complete: %d/%d valves open, %d forced open",
            valves_open_count,
            min_required,
            len(fallback_valves_opened),
        )

        return {
            "valves_open_count": valves_open_count,
            "min_required": min_required,
            "safety_satisfied": safety_satisfied,
            "fallback_valves_opened": fallback_valves_opened,
        }

    async def _force_open_valve(self, valve_id: str) -> None:
        """
        Force open a valve for safety.

        Args:
            valve_id: Valve switch entity ID

        Tasks:
            - Log warning
            - Call switch.turn_on service
            - Set valve lock
        """
        # Log warning
        _LOGGER.warning("Safety: Force opening valve %s", valve_id)

        try:
            # Call switch.turn_on service
            await self.hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": valve_id},
                blocking=True,
            )

            # Set valve lock
            config = await self.redis_client.get_config()
            valve_delay = config.get("valve_actuation_delay", 120)

            import time

            locked_until = time.time() + valve_delay
            await self.redis_client.set_valve_lock(
                valve_id,
                locked_until,
                reason="safety_force_open",
            )

            # Update zone valve state in Redis
            zone_ids = await self.redis_client.get_zone_ids()
            for zone_id in zone_ids:
                zone_state = await self.redis_client.get_zone_state(zone_id)
                if zone_state and zone_state.get("valve_id") == valve_id:
                    zone_state["valve_state"] = "open"
                    await self.redis_client.set_zone_state(zone_id, zone_state)
                    break

            _LOGGER.info("Safety: Successfully force opened valve %s", valve_id)

        except Exception as err:
            _LOGGER.error(
                "Safety: Failed to force open valve %s: %s",
                valve_id,
                err,
                exc_info=True,
            )
