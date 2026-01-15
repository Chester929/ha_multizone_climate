"""Valve control logic for multizone climate."""
from __future__ import annotations

from typing import Any
import logging
import time

_LOGGER = logging.getLogger(__name__)


class ValveController:
    """
    Controller for managing valve open/close operations.
    
    Handles:
    - Priority-based zone sorting
    - Valve action determination
    - Open-first-then-close sequence
    - Valve lock management
    - Minimum valves enforcement
    """

    def __init__(self, redis_client: Any, config: dict[str, Any]) -> None:
        """
        Initialize valve controller.
        
        Args:
            redis_client: Redis client for storing valve locks
            config: Configuration with min_valves_open, valve_actuation_delay
        """
        self.redis_client = redis_client
        self.config = config

    async def update_valves(
        self,
        zones: list[dict[str, Any]],
        main_climate_state: str,
        multizone_enabled: bool,
    ) -> list[dict[str, Any]]:
        """
        Determine and execute valve actions.
        
        Args:
            zones: List of climate zones with:
                - id: Zone identifier
                - state: Zone state (ON/OFF)
                - valve_id: Valve switch entity ID
                - current_temperature: Current zone temperature
                - target_temperature: Target zone temperature
                - satisfaction: Pre-calculated satisfaction state
                - priority: User-defined priority
                - is_fallback_valve: Is this a fallback valve
            main_climate_state: HVAC state (HEATING, COOLING, OFF)
            multizone_enabled: Whether multizone feature is active
        
        Returns:
            list: List of valve actions to execute:
                [
                    {"valve_id": "switch.bedroom_valve", "action": "open", "delay": 0},
                    {"valve_id": "switch.kitchen_valve", "action": "close", "delay": 120},
                ]
        
        Algorithm:
            1. If multizone disabled: individual zone valve control
            2. Calculate sort keys (priority, temperature deficit)
            3. Sort zones by priority
            4. Determine desired valve states based on satisfaction
            5. Apply safety rules (minimum valves open)
            6. Check valve locks
            7. Execute with open-first-then-close if at minimum
            8. Return action list
        """
        # If multizone disabled, each zone manages its own valve
        if not multizone_enabled:
            return self._determine_individual_valve_actions(zones, main_climate_state)
        
        # Calculate sort keys for all zones
        for zone in zones:
            zone["_sort_key"] = self._calculate_sort_key(zone, main_climate_state)
        
        # Sort zones by priority (highest first)
        sorted_zones = sorted(zones, key=lambda z: z["_sort_key"], reverse=True)
        
        # Determine desired valve states based on satisfaction
        valves_to_open = []
        valves_to_close = []
        
        for zone in sorted_zones:
            valve_id = zone.get("valve_id")
            if not valve_id:
                continue
            
            zone_state = zone.get("state", "OFF")
            satisfaction = zone.get("satisfaction", "unknown")
            
            # Zone turned OFF -> close valve (unless it's a required fallback)
            if zone_state == "OFF":
                valves_to_close.append(valve_id)
            elif main_climate_state.upper() == "HEATING":
                if satisfaction == "underheated":
                    valves_to_open.append(valve_id)
                elif satisfaction == "overheated":
                    valves_to_close.append(valve_id)
                elif satisfaction == "satisfied":
                    # Satisfied zones should have valves open to maintain temperature
                    valves_to_open.append(valve_id)
            elif main_climate_state.upper() == "COOLING":
                if satisfaction == "undercooled":
                    valves_to_open.append(valve_id)
                elif satisfaction == "overcooled":
                    valves_to_close.append(valve_id)
                elif satisfaction == "satisfied":
                    # Satisfied zones should have valves open to maintain temperature
                    valves_to_open.append(valve_id)
        
        # Apply minimum valves safety
        valves_to_open, valves_to_close = self._apply_minimum_valves_safety(
            valves_to_open, valves_to_close, zones
        )
        
        # Check valve locks (filter out locked valves)
        valves_to_open = await self._check_valve_locks(valves_to_open)
        valves_to_close = await self._check_valve_locks(valves_to_close)
        
        # Count currently open valves
        currently_open_count = sum(
            1 for zone in zones if zone.get("valve_state") == "open"
        )
        
        # Build action list with proper timing
        actions = self._build_action_list_with_timing(
            valves_to_open, valves_to_close, currently_open_count
        )
        
        # Set valve locks for all actions
        now = time.time()
        valve_actuation_delay = self.config.get("valve_actuation_delay", 120)
        
        for action in actions:
            await self.redis_client.set_valve_lock(
                action["valve_id"],
                now + valve_actuation_delay,
                f"valve_{action['action']}"
            )
        
        return actions

    def _calculate_sort_key(
        self, zone: dict[str, Any], hvac_state: str
    ) -> tuple[int, float]:
        """
        Calculate sort key for a zone.
        
        Args:
            zone: Zone data
            hvac_state: HVAC state (HEATING/COOLING)
        
        Returns:
            tuple: (priority, temperature_deficit)
        
        Heating mode: deficit = target - current
        Cooling mode: deficit = current - target
        OFF zones: (-1000, -1000) for lowest priority
        """
        if zone.get("state") == "OFF":
            return (-1000, -1000)
        
        current_temp = zone.get("current_temperature", 0.0)
        target_temp = zone.get("target_temperature", 0.0)
        priority = zone.get("priority", 0)
        
        if hvac_state.upper() == "HEATING":
            deficit = target_temp - current_temp
        else:  # COOLING
            deficit = current_temp - target_temp
        
        return (priority, deficit)

    def _determine_individual_valve_actions(
        self, zones: list[dict[str, Any]], hvac_state: str
    ) -> list[dict[str, Any]]:
        """
        Determine valve actions when multizone is disabled.
        
        Each zone manages its own valve:
        - Underheated/Undercooled: open valve
        - Overheated/Overcooled: close valve
        - Satisfied: maintain current state
        
        Args:
            zones: Zone list
            hvac_state: HVAC state
        
        Returns:
            list: Valve actions
        """
        actions = []
        
        for zone in zones:
            if zone.get("state") == "OFF":
                continue
            
            valve_id = zone.get("valve_id")
            if not valve_id:
                continue
            
            satisfaction = zone.get("satisfaction", "unknown")
            
            if hvac_state.upper() == "HEATING":
                if satisfaction == "underheated":
                    actions.append({"valve_id": valve_id, "action": "open", "delay": 0})
                elif satisfaction == "overheated":
                    actions.append({"valve_id": valve_id, "action": "close", "delay": 0})
            elif hvac_state.upper() == "COOLING":
                if satisfaction == "undercooled":
                    actions.append({"valve_id": valve_id, "action": "open", "delay": 0})
                elif satisfaction == "overcooled":
                    actions.append({"valve_id": valve_id, "action": "close", "delay": 0})
        
        return actions

    def _apply_minimum_valves_safety(
        self,
        valves_to_open: list[str],
        valves_to_close: list[str],
        zones: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        """
        Ensure minimum valves open requirement.
        
        Args:
            valves_to_open: List of valve IDs to open
            valves_to_close: List of valve IDs to close
            zones: All zones with current valve states
        
        Returns:
            tuple: (updated_valves_to_open, updated_valves_to_close)
        
        Logic:
            - Calculate how many will be open after actions
            - If below minimum, force open fallback valves
            - Remove forced valves from close list
        """
        # Get currently open valves
        currently_open = set()
        for zone in zones:
            if zone.get("valve_state") == "open":
                valve_id = zone.get("valve_id")
                if valve_id:
                    currently_open.add(valve_id)
        
        # Calculate what will be open after actions
        will_be_open = (currently_open - set(valves_to_close)) | set(valves_to_open)
        
        # Get minimum requirement
        min_valves_open = self.config.get("min_valves_open", 1)
        
        # Check if below minimum
        if len(will_be_open) < min_valves_open:
            shortage = min_valves_open - len(will_be_open)
            _LOGGER.warning(
                "Will have %d valves open, need %d. Forcing %d fallback valves open.",
                len(will_be_open),
                min_valves_open,
                shortage
            )
            
            # Get fallback valves sorted by priority
            fallback_valves = self._get_fallback_valves(zones, will_be_open)
            
            # Force open the required number of fallback valves
            for valve_id in fallback_valves[:shortage]:
                if valve_id not in valves_to_open:
                    valves_to_open.append(valve_id)
                # Remove from close list if present
                if valve_id in valves_to_close:
                    valves_to_close.remove(valve_id)
                    
                _LOGGER.info("Forcing fallback valve %s open for safety", valve_id)
        
        return (valves_to_open, valves_to_close)

    async def _check_valve_locks(
        self, valve_ids: list[str]
    ) -> list[str]:
        """
        Filter out locked valves.
        
        Args:
            valve_ids: List of valve IDs to check
        
        Returns:
            list: List of unlocked valve IDs
        """
        unlocked = []
        
        for valve_id in valve_ids:
            is_locked = await self.redis_client.is_valve_locked(valve_id)
            if not is_locked:
                unlocked.append(valve_id)
            else:
                _LOGGER.debug("Valve %s is locked, skipping action", valve_id)
        
        return unlocked

    def _build_action_list_with_timing(
        self,
        valves_to_open: list[str],
        valves_to_close: list[str],
        currently_open: int,
    ) -> list[dict[str, Any]]:
        """
        Build action list with proper timing for open-first-then-close.
        
        Args:
            valves_to_open: Valve IDs to open
            valves_to_close: Valve IDs to close
            currently_open: Number of currently open valves
        
        Returns:
            list: Actions with timing:
                [
                    {"valve_id": "...", "action": "open", "delay": 0, "timestamp": ...},
                    {"valve_id": "...", "action": "close", "delay": 120, "timestamp": ...},
                ]
        
        Logic:
            - If at minimum and swapping: open first, schedule close after delay
            - Otherwise: can open and close simultaneously
        """
        actions = []
        now = time.time()
        min_valves_open = self.config.get("min_valves_open", 1)
        valve_actuation_delay = self.config.get("valve_actuation_delay", 120)
        
        # Check if at minimum and need to swap
        at_minimum = currently_open == min_valves_open
        need_swap = len(valves_to_open) > 0 and len(valves_to_close) > 0
        
        if at_minimum and need_swap:
            # Open-first-then-close sequence
            _LOGGER.info(
                "At minimum valves (%d), using open-first-then-close sequence",
                min_valves_open
            )
            
            # Open new valves first (immediately)
            for valve_id in valves_to_open:
                actions.append({
                    "valve_id": valve_id,
                    "action": "open",
                    "delay": 0,
                    "timestamp": now
                })
            
            # Schedule closing of old valves after delay
            for valve_id in valves_to_close:
                actions.append({
                    "valve_id": valve_id,
                    "action": "close",
                    "delay": valve_actuation_delay,
                    "timestamp": now + valve_actuation_delay
                })
        else:
            # Normal operation: valves can open and close simultaneously
            for valve_id in valves_to_close:
                actions.append({
                    "valve_id": valve_id,
                    "action": "close",
                    "delay": 0,
                    "timestamp": now
                })
            
            for valve_id in valves_to_open:
                actions.append({
                    "valve_id": valve_id,
                    "action": "open",
                    "delay": 0,
                    "timestamp": now
                })
        
        return actions

    def _get_fallback_valves(
        self, zones: list[dict[str, Any]], exclude: set[str]
    ) -> list[str]:
        """
        Get fallback valve IDs for safety enforcement.
        
        Args:
            zones: All zones
            exclude: Valve IDs to exclude (already open)
        
        Returns:
            list: Fallback valve IDs sorted by priority
        """
        # Filter zones with is_fallback_valve=True
        fallback_zones = [
            zone for zone in zones
            if zone.get("is_fallback_valve", False)
        ]
        
        # Exclude already open/planned valves
        fallback_zones = [
            zone for zone in fallback_zones
            if zone.get("valve_id") not in exclude
        ]
        
        # Sort by priority (descending)
        fallback_zones.sort(key=lambda z: z.get("priority", 0), reverse=True)
        
        # Extract valve IDs
        return [zone["valve_id"] for zone in fallback_zones if zone.get("valve_id")]
