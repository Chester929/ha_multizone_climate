"""Safety checker for multizone climate system."""

from __future__ import annotations

from typing import Any
import logging

_LOGGER = logging.getLogger(__name__)


class SafetyChecker:
    """
    Safety checker to ensure minimum valves are open at all times.

    Prevents system damage by ensuring adequate flow through HVAC unit.
    """

    def __init__(self, redis_client: Any, config: dict[str, Any]) -> None:
        """
        Initialize safety checker.

        Args:
            redis_client: Redis client for accessing zone states
            config: Configuration with min_valves_open requirement
        """
        self.redis_client = redis_client
        self.config = config

    async def check_minimum_valves(self, zones: list[dict[str, Any]]) -> list[str]:
        """
        Check if minimum valves are open and force open fallback if needed.

        Args:
            zones: List of all zones with:
                - id: Zone identifier
                - valve_id: Valve switch entity ID
                - valve_state: Current valve state (open/closed)
                - is_fallback_valve: Is this a fallback valve
                - priority: Priority for fallback selection

        Returns:
            list: Valve IDs to force open (empty if safety satisfied)

        Algorithm:
            1. Count currently open valves
            2. Compare with min_valves_open requirement
            3. If below minimum:
               a. Log warning
               b. Calculate shortage
               c. Select fallback valves by priority
               d. Return valves to force open
            4. If OK, return empty list

        Example:
            min_valves_open = 2
            currently_open = 0
            -> Force open 2 fallback valves
        """
        currently_open_count = self._count_open_valves(zones)
        min_valves_open = self.config.get("min_valves_open", 1)

        if currently_open_count >= min_valves_open:
            return []

        shortage = min_valves_open - currently_open_count
        _LOGGER.warning(
            "Safety check: Only %d valves open, need %d",
            currently_open_count,
            min_valves_open,
        )

        fallback_valves = self._get_fallback_valves_sorted(zones, exclude_open=True)
        valves_to_force_open = fallback_valves[:shortage]

        for valve_id in valves_to_force_open:
            _LOGGER.warning("Safety: Force opening fallback valve %s", valve_id)

        return valves_to_force_open

    def _count_open_valves(self, zones: list[dict[str, Any]]) -> int:
        """
        Count currently open valves.

        Args:
            zones: List of zones with valve_state

        Returns:
            int: Number of open valves
        """
        return sum(1 for zone in zones if zone.get("valve_state") == "open")

    def _get_fallback_valves_sorted(
        self, zones: list[dict[str, Any]], exclude_open: bool = True
    ) -> list[str]:
        """
        Get fallback valve IDs sorted by priority.

        Args:
            zones: All zones
            exclude_open: If True, exclude already open valves

        Returns:
            list: Fallback valve IDs sorted by priority (highest first)

        Logic:
            - Filter zones with is_fallback_valve=True
            - Optionally exclude already open valves
            - Sort by priority (descending)
            - Return valve IDs
        """
        fallback_zones = [
            zone for zone in zones if zone.get("is_fallback_valve", False)
        ]

        if exclude_open:
            fallback_zones = [
                zone for zone in fallback_zones if zone.get("valve_state") != "open"
            ]

        fallback_zones.sort(key=lambda z: z.get("priority", 0), reverse=True)

        return [zone["valve_id"] for zone in fallback_zones if zone.get("valve_id")]
