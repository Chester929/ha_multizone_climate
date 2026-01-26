"""Core algorithms for multizone climate control."""

from __future__ import annotations

from typing import Any
import logging
import math

_LOGGER = logging.getLogger(__name__)


def calculate_main_target_temperature(
    zones: list[dict[str, Any]],
    config: dict[str, Any],
    current_main_target: float,
    main_current_temp: float | None = None,
) -> float | None:
    """
    Calculate the main HVAC target temperature based on zone targets.

    Implements dynamic heating boost algorithm for hydronic systems with three operating modes:
    - HEATING MODE: Any zone underheated - boost main target to provide hotter water
    - MAINTENANCE MODE: All zones satisfied - use slider/average logic
    - COOLING MODE: All zones overheated - reduce main target

    Args:
        zones: List of climate zones with the following keys:
            - id: Zone identifier
            - state: Zone state (ON/OFF)
            - target_temperature: Zone target temperature
            - current_temperature: Current zone temperature
            - satisfaction: Zone satisfaction state (underheated/satisfied/overheated)
        config: Configuration dict with keys:
            - use_average_mode: bool - Use average mode instead of slider
            - main_target_all_zones_satisfied: float (0.0-1.0) - Slider position
            - main_min_temp: float - Minimum main climate temperature
            - main_max_temp: float - Maximum main climate temperature
            - main_change_threshold: float - Minimum change to trigger update
        current_main_target: Current main climate target temperature
        main_current_temp: Current main climate temperature (optional, for dynamic boost)

    Returns:
        float: New main target temperature or None if no update needed

    Algorithm Operating Modes:

        HEATING MODE (any zone underheated):
            - Calculate maximum zone deficit: max(target - current) for underheated zones
            - Calculate main climate capability: current_main_target - main_current_temp
            - Required boost = max_zone_deficit - main_capability
            - New main target = current_main_target + required_boost
            - Clamp to configured limits

        MAINTENANCE MODE (all zones satisfied):
            - Use slider/average logic between zone targets
            - No boost applied

        IDLE MODE (all zones overheated):
            - Reduce main target to minimum of overheated zone targets
            - Allows system to cool down naturally
            - Valves closed, HVAC in idle state

    Example (Heating Mode):
        Zone B: current=22.0°C, target=24.0°C → deficit = 2.0°C
        Main: current=23.0°C, target=23.7°C → capability = 0.7°C
        Required boost = 2.0 - 0.7 = 1.3°C
        New main target = 23.7 + 1.3 = 25.0°C ✅
    """
    if not zones:
        return None

    # Filter active zones (state != OFF)
    active_zones = [z for z in zones if z.get("state") != "OFF"]
    if not active_zones:
        return None

    # Categorize zones by satisfaction state
    underheated_zones = [z for z in active_zones if z.get("satisfaction") == "underheated"]
    satisfied_zones = [z for z in active_zones if z.get("satisfaction") == "satisfied"]
    overheated_zones = [z for z in active_zones if z.get("satisfaction") == "overheated"]

    # Determine operating mode
    if underheated_zones:
        # HEATING MODE: At least one zone needs heating
        _LOGGER.debug(
            "HEATING MODE: %d underheated, %d satisfied, %d overheated zones",
            len(underheated_zones),
            len(satisfied_zones),
            len(overheated_zones),
        )
        
        # Calculate maximum zone deficit (how much heating is needed)
        max_zone_deficit = 0.0
        for zone in underheated_zones:
            current_temp = zone.get("current_temperature")
            target_temp = zone.get("target_temperature")
            if current_temp is not None and target_temp is not None:
                deficit = target_temp - current_temp
                if deficit > max_zone_deficit:
                    max_zone_deficit = deficit
                    _LOGGER.debug(
                        "Zone %s deficit: %.1f°C (%.1f -> %.1f)",
                        zone.get("id", "unknown"),
                        deficit,
                        current_temp,
                        target_temp,
                    )
        
        # Calculate main climate capability (how much it can heat now)
        main_capability = 0.0
        if main_current_temp is not None:
            main_capability = current_main_target - main_current_temp
            _LOGGER.debug(
                "Main climate capability: %.1f°C (target %.1f - current %.1f)",
                main_capability,
                current_main_target,
                main_current_temp,
            )
        else:
            _LOGGER.debug("Main current temp not available, assuming capability = 0")
        
        # Calculate required boost
        required_boost = max(0.0, max_zone_deficit - main_capability)
        
        # Calculate new main target with boost
        main_target_raw = current_main_target + required_boost
        
        _LOGGER.info(
            "HEATING MODE: max_deficit=%.1f, capability=%.1f, boost=%.1f, new_target_raw=%.1f",
            max_zone_deficit,
            main_capability,
            required_boost,
            main_target_raw,
        )
        
    elif satisfied_zones:
        # MAINTENANCE MODE: All zones satisfied
        _LOGGER.debug("MAINTENANCE MODE: All %d zones satisfied", len(satisfied_zones))
        
        zone_targets = [z["target_temperature"] for z in satisfied_zones]
        
        # Calculate main target based on mode
        if config.get("use_average_mode", False):
            # True average
            main_target_raw = sum(zone_targets) / len(zone_targets)
        else:
            # Slider-based linear interpolation
            min_target = min(zone_targets)
            max_target = max(zone_targets)
            
            slider = config.get("main_target_all_zones_satisfied", 0.5)
            if min_target == max_target:
                main_target_raw = min_target
            else:
                main_target_raw = min_target + slider * (max_target - min_target)
        
        _LOGGER.info("MAINTENANCE MODE: target=%.1f", main_target_raw)
        
    elif overheated_zones:
        # IDLE MODE: All zones overheated (valves closed, system idle)
        _LOGGER.debug("IDLE MODE: All %d zones overheated", len(overheated_zones))
        
        zone_targets = [z["target_temperature"] for z in overheated_zones]
        
        # Reduce main target to minimum of overheated zones to cool down naturally
        main_target_raw = min(zone_targets)
        
        _LOGGER.info("IDLE MODE: target=%.1f (min of overheated zones, system idle)", main_target_raw)
        
    else:
        # No active zones with valid satisfaction state
        return None

    # Round to nearest 0.5°C increment
    main_target_rounded = round_to_half_degree(main_target_raw)

    # Clamp to configured limits
    main_target = clamp_temperature(
        main_target_rounded,
        config.get("main_min_temp", 18.0),
        config.get("main_max_temp", 30.0),
    )

    # Only return if change exceeds threshold
    threshold = config.get("main_change_threshold", 0.5)
    if abs(main_target - current_main_target) >= threshold:
        _LOGGER.info(
            "Main target updated: %.1f°C -> %.1f°C (change: %.1f°C)",
            current_main_target,
            main_target,
            main_target - current_main_target,
        )
        return main_target

    _LOGGER.debug(
        "Main target unchanged: %.1f°C (change %.1f°C below threshold %.1f°C)",
        current_main_target,
        abs(main_target - current_main_target),
        threshold,
    )
    return None


def round_to_half_degree(temperature: float) -> float:
    """
    Round temperature to nearest 0.5°C increment.

    Args:
        temperature: Temperature value to round

    Returns:
        float: Rounded temperature

    Examples:
        22.3 -> 22.5
        22.2 -> 22.0
        21.75 -> 22.0
        21.25 -> 21.5
    """
    return math.floor(temperature * 2 + 0.5) / 2


def clamp_temperature(temperature: float, min_temp: float, max_temp: float) -> float:
    """
    Clamp temperature to configured limits.

    Args:
        temperature: Temperature to clamp
        min_temp: Minimum allowed temperature
        max_temp: Maximum allowed temperature

    Returns:
        float: Clamped temperature

    Examples:
        clamp_temperature(17.0, 18.0, 30.0) -> 18.0
        clamp_temperature(32.0, 18.0, 30.0) -> 30.0
        clamp_temperature(25.0, 18.0, 30.0) -> 25.0
    """
    return max(min_temp, min(max_temp, temperature))
