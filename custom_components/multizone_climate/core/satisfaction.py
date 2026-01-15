"""Zone satisfaction state machine logic."""
from __future__ import annotations

from typing import Literal
import logging

_LOGGER = logging.getLogger(__name__)

# Type definitions for satisfaction states
SatisfactionState = Literal[
    "underheated", "satisfied", "overheated", "undercooled", "overcooled", "unknown"
]
TemperatureDirection = Literal["rising", "falling", "stable"]
HVACMode = Literal["heating", "cooling", "off"]


class ZoneSatisfactionStateMachine:
    """
    State machine for managing zone satisfaction states with hysteresis.
    
    Handles state transitions for both heating and cooling modes.
    Uses hysteresis to prevent rapid state changes (chattering).
    """

    def __init__(
        self,
        target_temperature: float,
        opening_offset: float,
        closing_offset: float,
        satisfaction_eps: float,
    ) -> None:
        """
        Initialize satisfaction state machine.
        
        Args:
            target_temperature: Target temperature for the zone
            opening_offset: Temperature below target to trigger valve opening
            closing_offset: Temperature above target to trigger valve closing
            satisfaction_eps: Epsilon around target for satisfaction determination
        
        Example:
            target = 21.0, opening_offset = 0.3, closing_offset = 0.3, satisfaction_eps = 0.1
            Lower bound: 20.7 (target - opening_offset)
            Upper bound: 21.3 (target + closing_offset)
            Satisfied entry (from underheated): 21.1 (target + eps)
            Satisfied exit (from overheated): 20.9 (target - eps)
        """
        self.target_temperature = target_temperature
        self.opening_offset = opening_offset
        self.closing_offset = closing_offset
        self.satisfaction_eps = satisfaction_eps
        # TODO: Calculate bounds
        # TODO: Store current state

    def update_state(
        self,
        current_temperature: float,
        previous_temperature: float,
        current_state: SatisfactionState,
        hvac_mode: HVACMode,
    ) -> tuple[SatisfactionState, TemperatureDirection]:
        """
        Update satisfaction state based on current temperature.
        
        Args:
            current_temperature: Current zone temperature
            previous_temperature: Previous zone temperature
            current_state: Current satisfaction state
            hvac_mode: HVAC mode (heating/cooling)
        
        Returns:
            tuple: (new_satisfaction_state, temperature_direction)
        
        State Transitions (Heating):
            Underheated -> Satisfied: temp >= target + satisfaction_eps (while rising)
            Satisfied -> Overheated: temp > target + closing_offset
            Overheated -> Satisfied: temp <= target - satisfaction_eps (while falling)
            Satisfied -> Underheated: temp < target - opening_offset
        
        State Transitions (Cooling):
            Undercooled -> Satisfied: temp <= target - satisfaction_eps (while falling)
            Satisfied -> Overcooled: temp < target - closing_offset
            Overcooled -> Satisfied: temp >= target + satisfaction_eps (while rising)
            Satisfied -> Undercooled: temp > target + opening_offset
        """
        # TODO: Determine temperature direction
        # TODO: Calculate bounds
        # TODO: Apply state machine logic based on hvac_mode
        # TODO: Return new state and direction
        return ("unknown", "stable")

    def _update_heating_state(
        self,
        current_temperature: float,
        current_state: SatisfactionState,
        temp_direction: TemperatureDirection,
    ) -> SatisfactionState:
        """
        Update state for heating mode.
        
        Args:
            current_temperature: Current temperature
            current_state: Current satisfaction state
            temp_direction: Temperature direction (rising/falling)
        
        Returns:
            SatisfactionState: New satisfaction state
        
        Logic:
            - Underheated: temp < lower_bound (target - opening_offset)
            - Overheated: temp > upper_bound (target + closing_offset)
            - Satisfied: between bounds with hysteresis
        """
        # TODO: Implement heating mode state transitions
        return "unknown"

    def _update_cooling_state(
        self,
        current_temperature: float,
        current_state: SatisfactionState,
        temp_direction: TemperatureDirection,
    ) -> SatisfactionState:
        """
        Update state for cooling mode.
        
        Args:
            current_temperature: Current temperature
            current_state: Current satisfaction state
            temp_direction: Temperature direction (rising/falling)
        
        Returns:
            SatisfactionState: New satisfaction state
        
        Logic:
            - Undercooled: temp > upper_bound (target + opening_offset)
            - Overcooled: temp < lower_bound (target - closing_offset)
            - Satisfied: between bounds with hysteresis
        """
        # TODO: Implement cooling mode state transitions
        return "unknown"

    def _determine_direction(
        self, current_temp: float, previous_temp: float
    ) -> TemperatureDirection:
        """
        Determine temperature direction.
        
        Args:
            current_temp: Current temperature
            previous_temp: Previous temperature
        
        Returns:
            TemperatureDirection: rising, falling, or stable
        """
        # TODO: Compare temperatures
        # TODO: Return direction
        return "stable"
