"""Valve state change automation."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.core import Event, callback, EventStateChangedData
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


class ValveStateChangeAutomation:
    """
    Automation triggered by valve switch/valve entity state changes.

    Listens for:
    - Zone valve switch state changes (on/off)

    Actions:
    - Update valve_state in Redis (opened/closed)
    """

    def __init__(self, hass: Any, redis_client: Any) -> None:
        """
        Initialize automation.

        Args:
            hass: Home Assistant instance
            redis_client: Redis client for state updates
        """
        self.hass = hass
        self.redis_client = redis_client
        self._cancel_listeners: list = []
        # Mapping from entity_id to zone_id for O(1) lookups
        self._entity_to_zone: dict[str, str] = {}

    async def setup(self) -> None:
        """
        Set up automation listeners.

        Tasks:
            - Register state change listeners for all zone valve switches
            - Build entity_id to zone_id mapping for efficient lookups
        """
        zone_ids = await self.redis_client.get_zone_ids()
        valve_entity_ids: list[str] = []

        # Build mapping and collect entity IDs
        for zone_id in zone_ids:
            zone_state = await self.redis_client.get_zone_state(zone_id)
            if zone_state and "valve_switch_entity_id" in zone_state:
                entity_id = zone_state["valve_switch_entity_id"]
                if isinstance(entity_id, str):
                    valve_entity_ids.append(entity_id)
                    self._entity_to_zone[entity_id] = zone_id

        if valve_entity_ids:
            cancel = async_track_state_change_event(
                self.hass, valve_entity_ids, self._handle_valve_state_change
            )
            self._cancel_listeners.append(cancel)
            _LOGGER.info(
                "Valve state change automation listening to %d valve switches",
                len(valve_entity_ids),
            )

    @callback
    def _handle_valve_state_change(self, event: Event[EventStateChangedData]) -> None:
        """
        Handle valve switch state change.

        Args:
            event: State change event

        Tasks:
            - Get entity_id from event
            - Find corresponding zone
            - Map HA state (on/off) to valve state (opened/closed)
            - Update zone valve_state in Redis
        """
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]

        # Ignore if new_state is None (entity removed)
        if new_state is None:
            return

        # Ignore if state didn't actually change
        if old_state and old_state.state == new_state.state:
            return

        # Map HA state to valve state
        ha_state = new_state.state
        if ha_state == "on":
            valve_state = "opened"
        elif ha_state == "off":
            valve_state = "closed"
        else:
            # Unknown state, log and skip
            _LOGGER.debug(
                "Valve switch %s has unknown state %s, skipping update",
                entity_id,
                ha_state,
            )
            return

        # Update Redis asynchronously
        self.hass.async_create_task(
            self._update_valve_state_in_redis(entity_id, valve_state)
        )

    async def _update_valve_state_in_redis(
        self, entity_id: str, valve_state: str
    ) -> None:
        """
        Update valve state in Redis for the zone.

        Args:
            entity_id: Valve switch entity ID
            valve_state: New valve state ("opened" or "closed")

        Tasks:
            - Use mapping to find zone by valve_switch_entity_id (O(1))
            - Update zone valve_state
            - Write to Redis
        """
        try:
            # Use mapping for O(1) lookup
            zone_id = self._entity_to_zone.get(entity_id)
            if not zone_id:
                _LOGGER.warning(
                    "No zone found with valve_switch_entity_id %s", entity_id
                )
                return

            zone_state = await self.redis_client.get_zone_state(zone_id)
            if not zone_state:
                _LOGGER.warning("Zone state not found for zone %s", zone_id)
                return

            old_valve_state = zone_state.get("valve_state", "unknown")
            zone_state["valve_state"] = valve_state
            await self.redis_client.set_zone_state(zone_id, zone_state)
            _LOGGER.debug(
                "Updated valve state for zone %s (entity %s): %s -> %s",
                zone_id,
                entity_id,
                old_valve_state,
                valve_state,
            )
        except Exception as err:
            _LOGGER.error(
                "Error updating valve state in Redis for %s: %s",
                entity_id,
                err,
                exc_info=True,
            )

    async def stop(self) -> None:
        """Stop the automation and cleanup listeners."""
        for cancel in self._cancel_listeners:
            cancel()
        self._cancel_listeners.clear()
        # Clear mapping
        self._entity_to_zone.clear()
