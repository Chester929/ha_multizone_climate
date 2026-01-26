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
            opening_offset: Temperature offset for valve opening control (valve logic, not satisfaction)
            closing_offset: Temperature offset for valve closing control (valve logic, not satisfaction)
            satisfaction_eps: Epsilon for satisfaction state determination (satisfaction boundaries)

        Note:
            Valve control and satisfaction states are separate:
            - Valve control uses opening_offset and closing_offset
            - Satisfaction states use satisfaction_eps for boundaries
            
        Example:
            target = 22.0, opening_offset = 0.3, closing_offset = 0.3, satisfaction_eps = 0.1
            
            Satisfaction state boundaries (using eps):
            - Underheated: temp < 21.9 (target - eps)
            - Satisfied: 21.9 <= temp <= 22.1 (target ± eps)
            - Overheated: temp > 22.1 (target + eps)
            
            Valve control boundaries (using offsets, separate logic):
            - Valve opens: temp < 21.7 (target - opening_offset)
            - Valve closes: temp > 22.3 (target + closing_offset)
        """
        self.target_temperature = target_temperature
        self.opening_offset = opening_offset
        self.closing_offset = closing_offset
        self.satisfaction_eps = satisfaction_eps

        # Calculate bounds for satisfaction state determination (using eps)
        # Satisfaction states are based on proximity to target
        self.satisfied_lower = target_temperature - satisfaction_eps
        self.satisfied_upper = target_temperature + satisfaction_eps
        
        # Valve control uses opening_offset and closing_offset (separate from satisfaction)
        self.valve_lower_bound = target_temperature - opening_offset
        self.valve_upper_bound = target_temperature + closing_offset

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
            Underheated: temp < (target - satisfaction_eps)
            Satisfied: (target - satisfaction_eps) <= temp <= (target + satisfaction_eps)
            Overheated: temp > (target + satisfaction_eps)
            
            Transitions with hysteresis:
            - Underheated -> Satisfied: temp >= (target + satisfaction_eps) while rising
            - Satisfied -> Underheated: temp < (target - satisfaction_eps) while falling
            - Satisfied -> Overheated: temp > (target + satisfaction_eps) while rising
            - Overheated -> Satisfied: temp <= (target - satisfaction_eps) while falling

        State Transitions (Cooling):
            Undercooled: temp > (target + satisfaction_eps)
            Satisfied: (target - satisfaction_eps) <= temp <= (target + satisfaction_eps)
            Overcooled: temp < (target - satisfaction_eps)
            
            Transitions with hysteresis:
            - Undercooled -> Satisfied: temp <= (target - satisfaction_eps) while falling
            - Satisfied -> Undercooled: temp > (target + satisfaction_eps) while rising
            - Satisfied -> Overcooled: temp < (target - satisfaction_eps) while falling
            - Overcooled -> Satisfied: temp >= (target + satisfaction_eps) while rising
            
        Note: Valve control uses opening_offset and closing_offset (separate logic).
        """
        # Determine temperature direction
        temp_direction = self._determine_direction(
            current_temperature, previous_temperature
        )

        # Apply state machine logic based on HVAC mode
        new_state: SatisfactionState
        if hvac_mode == "off":
            new_state = "unknown"
        elif hvac_mode == "heating":
            new_state = self._update_heating_state(
                current_temperature, current_state, temp_direction
            )
        elif hvac_mode == "cooling":
            new_state = self._update_cooling_state(
                current_temperature, current_state, temp_direction
            )
        else:
            new_state = "unknown"

        return (new_state, temp_direction)

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

        Logic (using satisfaction_eps for state boundaries):
            - Underheated: temp < (target - satisfaction_eps)
            - Satisfied: (target - satisfaction_eps) <= temp <= (target + satisfaction_eps)
            - Overheated: temp > (target + satisfaction_eps)
        """
        # Check if currently overheated (above satisfaction upper bound)
        if current_temperature > self.satisfied_upper:
            # If we're overheated, stay overheated until we reach target - eps while falling
            if current_state == "overheated":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_lower
                ):
                    return "satisfied"
                return "overheated"
            # Any other state -> overheated when exceeding upper satisfaction bound
            return "overheated"

        # Check if currently underheated (below satisfaction lower bound)
        if current_temperature < self.satisfied_lower:
            # If we're underheated, stay underheated until we reach target + eps while rising
            if current_state == "underheated":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_upper
                ):
                    return "satisfied"
                return "underheated"
            # Any other state -> underheated when falling below lower satisfaction bound
            return "underheated"

        # Between satisfaction bounds - handle hysteresis
        # If currently underheated, check for transition to satisfied
        if current_state == "underheated":
            # Must reach target + eps while rising to become satisfied
            if (
                temp_direction == "rising"
                and current_temperature >= self.satisfied_upper
            ):
                return "satisfied"
            return "underheated"

        # If currently overheated, check for transition to satisfied
        if current_state == "overheated":
            # Must reach target - eps while falling to become satisfied
            if (
                temp_direction == "falling"
                and current_temperature <= self.satisfied_lower
            ):
                return "satisfied"
            return "overheated"

        # If currently satisfied or unknown, stay/become satisfied (within satisfaction bounds)
        return "satisfied"

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

        Logic (using satisfaction_eps for state boundaries):
            - Undercooled: temp > (target + satisfaction_eps)
            - Satisfied: (target - satisfaction_eps) <= temp <= (target + satisfaction_eps)
            - Overcooled: temp < (target - satisfaction_eps)
        """
        # Check if currently undercooled (above satisfaction upper bound - needs cooling)
        if current_temperature > self.satisfied_upper:
            # If we're undercooled, stay undercooled until we reach target - eps while falling
            if current_state == "undercooled":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_lower
                ):
                    return "satisfied"
                return "undercooled"
            # Any other state -> undercooled when exceeding upper satisfaction bound
            return "undercooled"

        # Check if currently overcooled (below satisfaction lower bound - too cool)
        if current_temperature < self.satisfied_lower:
            # If we're overcooled, stay overcooled until we reach target + eps while rising
            if current_state == "overcooled":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_upper
                ):
                    return "satisfied"
                return "overcooled"
            # Any other state -> overcooled when falling below lower satisfaction bound
            return "overcooled"

        # Between satisfaction bounds - handle hysteresis
        # If currently undercooled, check for transition to satisfied
        if current_state == "undercooled":
            # Must reach target - eps while falling to become satisfied
            if (
                temp_direction == "falling"
                and current_temperature <= self.satisfied_lower
            ):
                return "satisfied"
            return "undercooled"

        # If currently overcooled, check for transition to satisfied
        if current_state == "overcooled":
            # Must reach target + eps while rising to become satisfied
            if (
                temp_direction == "rising"
                and current_temperature >= self.satisfied_upper
            ):
                return "satisfied"
            return "overcooled"

        # If currently satisfied or unknown, stay/become satisfied (within satisfaction bounds)
        return "satisfied"

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
        if current_temp > previous_temp:
            return "rising"
        if current_temp < previous_temp:
            return "falling"
        return "stable"
