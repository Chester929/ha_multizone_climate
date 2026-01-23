"""Update valves background job."""

from __future__ import annotations

from typing import Any
import logging

from .base import BaseJob
from ..core.valve_control import ValveController

_LOGGER = logging.getLogger(__name__)


class UpdateValvesJob(BaseJob):
    """
    Background job to update valve states based on zone satisfaction.

    Triggered when:
    - Zone temperatures change
    - Zone targets change
    - Calculate main temp job completes
    """

    def __init__(self, redis_client: Any, hass: Any) -> None:
        """
        Initialize update valves job.

        Args:
            redis_client: Redis client for data access
            hass: Home Assistant instance
        """
        super().__init__("update_valves", redis_client, hass)
        self.valve_controller: ValveController | None = None

    async def _execute_impl(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute valve update logic.

        Args:
            job_data: Job parameters

        Returns:
            dict: Result with:
                - valves_opened: List of valve IDs opened
                - valves_closed: List of valve IDs closed
                - valves_unchanged: List of valve IDs unchanged
                - actions_taken: Number of actions executed

        Steps:
            1. Fetch config and zone states from Redis
            2. Get main climate HVAC state
            3. Get multizone enabled status
            4. Call ValveController.update_valves()
            5. Execute valve actions (open/close service calls)
            6. Set valve locks in Redis
            7. Update zone valve states in Redis
            8. Return result
        """
        _LOGGER.debug("Starting update valves job: %s", job_data)

        # Fetch config
        config = await self.redis_client.get_config()
        if not config:
            _LOGGER.warning("No config found in Redis")
            return {"error": "no_config"}

        # Initialize valve controller with config
        if not self.valve_controller:
            self.valve_controller = ValveController(self.redis_client, config)

        # Fetch zone states
        zone_ids = await self.redis_client.get_zone_ids()
        zones = []
        for zone_id in zone_ids:
            state = await self.redis_client.get_zone_state(zone_id)
            if state:
                state["id"] = zone_id
                zones.append(state)

        # Get main climate state
        main_climate = await self.redis_client.get_main_climate_state()
        main_climate_state = main_climate.get("hvac_action", "OFF")

        # Get multizone enabled
        multizone_enabled = config.get("multizone_enabled", False)

        # Call valve_controller.update_valves()
        valve_actions = await self.valve_controller.update_valves(
            zones=zones,
            main_climate_state=main_climate_state,
            multizone_enabled=multizone_enabled,
        )

        # Execute valve actions
        valves_opened = []
        valves_closed = []
        valves_unchanged = []

        for action in valve_actions:
            valve_id = action.get("valve_id")
            action_type = action.get("action")

            if action_type == "open":
                await self._execute_valve_action(action)
                valves_opened.append(valve_id)
            elif action_type == "close":
                await self._execute_valve_action(action)
                valves_closed.append(valve_id)
            else:
                valves_unchanged.append(valve_id)

        _LOGGER.info(
            "Valve update complete: %d opened, %d closed, %d unchanged",
            len(valves_opened),
            len(valves_closed),
            len(valves_unchanged),
        )

        return {
            "valves_opened": valves_opened,
            "valves_closed": valves_closed,
            "valves_unchanged": valves_unchanged,
            "actions_taken": len(valves_opened) + len(valves_closed),
        }

    async def _execute_valve_action(self, action: dict[str, Any]) -> None:
        """
        Execute a single valve action.

        Args:
            action: Valve action dict:
                - valve_id: Valve switch entity ID
                - action: "open" or "close"
                - delay: Delay before executing (seconds)

        Tasks:
            - If delay > 0, schedule action
            - Otherwise, call switch.turn_on or switch.turn_off service
        """
        valve_id = action.get("valve_id")
        action_type = action.get("action")
        delay = action.get("delay", 0)

        if not valve_id or not action_type:
            _LOGGER.warning("Invalid valve action: missing valve_id or action")
            return

        if delay > 0:
            # Schedule action with delay
            _LOGGER.debug(
                "Scheduling %s for %s with delay %ds",
                action_type,
                valve_id,
                delay,
            )
            self.hass.loop.call_later(
                delay,
                lambda: self.hass.async_create_task(
                    self._execute_valve_service_call(str(valve_id), str(action_type))
                ),
            )
        else:
            # Execute immediately
            await self._execute_valve_service_call(str(valve_id), str(action_type))

    async def _execute_valve_service_call(
        self, valve_id: str, action_type: str
    ) -> None:
        """
        Execute the actual valve service call.

        Args:
            valve_id: Valve switch entity ID
            action_type: "open" or "close"
        """
        try:
            service = "turn_on" if action_type == "open" else "turn_off"

            await self.hass.services.async_call(
                "switch",
                service,
                {"entity_id": valve_id},
                blocking=True,
            )

            _LOGGER.debug("%s valve %s", action_type.capitalize(), valve_id)

            # Set valve lock to prevent re-actuation
            config = await self.redis_client.get_config()
            valve_delay = config.get("valve_actuation_delay", 120)

            import time

            locked_until = time.time() + valve_delay
            await self.redis_client.set_valve_lock(
                valve_id,
                locked_until,
                reason=f"valve_{action_type}",
            )

            # Update zone valve state in Redis
            # Find zone by valve_id
            zone_ids = await self.redis_client.get_zone_ids()
            for zone_id in zone_ids:
                zone_state = await self.redis_client.get_zone_state(zone_id)
                if zone_state and zone_state.get("valve_id") == valve_id:
                    zone_state["valve_state"] = (
                        action_type + "ed"
                    )  # "opened" or "closed"
                    await self.redis_client.set_zone_state(zone_id, zone_state)
                    break

        except Exception as err:
            _LOGGER.error(
                "Failed to %s valve %s: %s",
                action_type,
                valve_id,
                err,
                exc_info=True,
            )
