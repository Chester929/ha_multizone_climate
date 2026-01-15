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

        # Calculate bounds for state determination
        self.lower_bound = target_temperature - opening_offset
        self.upper_bound = target_temperature + closing_offset
        self.satisfied_entry_heating = target_temperature + satisfaction_eps
        self.satisfied_exit_heating = target_temperature - satisfaction_eps

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
        # Determine temperature direction
        temp_direction = self._determine_direction(
            current_temperature, previous_temperature
        )

        # Apply state machine logic based on HVAC mode
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

        Logic:
            - Underheated: temp < lower_bound (target - opening_offset)
            - Overheated: temp > upper_bound (target + closing_offset)
            - Satisfied: between bounds with hysteresis
        """
        # Check if currently overheated (above upper bound)
        if current_temperature > self.upper_bound:
            # If we're overheated, stay overheated until we reach target - eps while falling
            if current_state == "overheated":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_exit_heating
                ):
                    return "satisfied"
                return "overheated"
            else:
                # Any other state -> overheated when exceeding upper bound
                return "overheated"

        # Check if currently underheated (below lower bound)
        elif current_temperature < self.lower_bound:
            # If we're underheated, stay underheated until we reach target + eps while rising
            if current_state == "underheated":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_heating
                ):
                    return "satisfied"
                return "underheated"
            else:
                # Any other state -> underheated when falling below lower bound
                return "underheated"

        # Between bounds - handle hysteresis
        else:
            # If currently underheated, check for transition to satisfied
            if current_state == "underheated":
                # Must reach target + eps while rising to become satisfied
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_heating
                ):
                    return "satisfied"
                return "underheated"

            # If currently overheated, check for transition to satisfied
            elif current_state == "overheated":
                # Must reach target - eps while falling to become satisfied
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_exit_heating
                ):
                    return "satisfied"
                return "overheated"

            # If currently satisfied or unknown, stay/become satisfied (within bounds)
            else:
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

        Logic:
            - Undercooled: temp > upper_bound (target + opening_offset)
            - Overcooled: temp < lower_bound (target - closing_offset)
            - Satisfied: between bounds with hysteresis
        """
        # Check if currently undercooled (above upper bound - needs cooling)
        if current_temperature > self.upper_bound:
            # If we're undercooled, stay undercooled until we reach target - eps while falling
            if current_state == "undercooled":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_exit_heating
                ):
                    return "satisfied"
                return "undercooled"
            else:
                # Any other state -> undercooled when exceeding upper bound
                return "undercooled"

        # Check if currently overcooled (below lower bound - too cool)
        elif current_temperature < self.lower_bound:
            # If we're overcooled, stay overcooled until we reach target + eps while rising
            if current_state == "overcooled":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_heating
                ):
                    return "satisfied"
                return "overcooled"
            else:
                # Any other state -> overcooled when falling below lower bound
                return "overcooled"

        # Between bounds - handle hysteresis
        else:
            # If currently undercooled, check for transition to satisfied
            if current_state == "undercooled":
                # Must reach target - eps while falling to become satisfied
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_exit_heating
                ):
                    return "satisfied"
                return "undercooled"

            # If currently overcooled, check for transition to satisfied
            elif current_state == "overcooled":
                # Must reach target + eps while rising to become satisfied
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_heating
                ):
                    return "satisfied"
                return "overcooled"

            # If currently satisfied or unknown, stay/become satisfied (within bounds)
            else:
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
        elif current_temp < previous_temp:
            return "falling"
        else:
            return "stable"
