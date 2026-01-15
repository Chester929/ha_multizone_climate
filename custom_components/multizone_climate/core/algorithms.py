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
) -> float | None:
    """
    Calculate the main HVAC target temperature based on zone targets.

    Implements two calculation methods:
    - Slider-based: Linear interpolation between min and max zone targets
    - Average mode: Arithmetic mean of all active zone targets

    Args:
        zones: List of climate zones with the following keys:
            - id: Zone identifier
            - state: Zone state (ON/OFF)
            - target_temperature: Zone target temperature
            - satisfaction: Zone satisfaction state (underheated/satisfied/overheated)
        config: Configuration dict with keys:
            - use_average_mode: bool - Use average mode instead of slider
            - main_target_all_zones_satisfied: float (0.0-1.0) - Slider position
            - main_min_temp: float - Minimum main climate temperature
            - main_max_temp: float - Maximum main climate temperature
            - main_change_threshold: float - Minimum change to trigger update
        current_main_target: Current main climate target temperature

    Returns:
        float: New main target temperature or None if no update needed

    Algorithm Steps:
        1. Filter active zones (state != OFF)
        2. Exclude overheated zones from calculation
        3. Calculate target based on mode:
           a. Average mode: mean of all zone targets
           b. Slider mode: min + slider × (max - min)
        4. Round to nearest 0.5°C increment
        5. Clamp to configured limits
        6. Only return if change exceeds threshold

    Example:
        zones = [
            {
                "id": "bedroom",
                "state": "ON",
                "target_temperature": 20.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "state": "ON",
                "target_temperature": 22.0,
                "satisfaction": "satisfied",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(zones, config, 20.5)
        # Returns: 21.0 (midpoint between 20 and 22)
    """
    if not zones:
        return None

    # Filter active zones (state != OFF)
    active_zones = [z for z in zones if z.get("state") != "OFF"]
    if not active_zones:
        return None

    # Exclude overheated zones from calculation
    non_overheated_zones = [
        z for z in active_zones if z.get("satisfaction") != "overheated"
    ]

    # If all zones are overheated, use fallback logic (use all active zones)
    if not non_overheated_zones:
        zone_targets = [z["target_temperature"] for z in active_zones]
    else:
        zone_targets = [z["target_temperature"] for z in non_overheated_zones]

    # Calculate main target based on mode
    if config.get("use_average_mode", False):
        # Choice B: True average
        main_target_raw = sum(zone_targets) / len(zone_targets)
    else:
        # Choice A: Slider-based linear interpolation
        min_target = min(zone_targets)
        max_target = max(zone_targets)

        slider = config.get("main_target_all_zones_satisfied", 0.5)
        if min_target == max_target:
            main_target_raw = min_target
        else:
            main_target_raw = min_target + slider * (max_target - min_target)

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
        return main_target

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
