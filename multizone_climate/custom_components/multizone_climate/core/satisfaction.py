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
            
            Entering satisfied (uses eps):
            - From underheated: at 22.1 (target + eps) while rising
            - From overheated: at 21.9 (target - eps) while falling
            
            Exiting satisfied (uses offsets - wider range):
            - To underheated: at 21.7 (target - opening_offset) while falling
            - To overheated: at 22.3 (target + closing_offset) while rising
            
            Valve control boundaries (using offsets, separate logic):
            - Valve opens: temp < 21.7 (target - opening_offset)
            - Valve closes: temp > 22.3 (target + closing_offset)
        """
        self.target_temperature = target_temperature
        self.opening_offset = opening_offset
        self.closing_offset = closing_offset
        self.satisfaction_eps = satisfaction_eps

        # Calculate bounds for entering satisfied state (using eps - narrower range)
        self.satisfied_entry_lower = target_temperature - satisfaction_eps
        self.satisfied_entry_upper = target_temperature + satisfaction_eps
        
        # Calculate bounds for exiting satisfied state (using offsets - wider range)
        self.satisfied_exit_lower = target_temperature - opening_offset
        self.satisfied_exit_upper = target_temperature + closing_offset

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
            Entering satisfied (uses satisfaction_eps):
            - Underheated → Satisfied: temp >= (target + satisfaction_eps) while rising
            - Overheated → Satisfied: temp <= (target - satisfaction_eps) while falling
            
            Exiting satisfied (uses opening/closing offsets - wider range):
            - Satisfied → Underheated: temp < (target - opening_offset) while falling
            - Satisfied → Overheated: temp > (target + closing_offset) while rising

        State Transitions (Cooling):
            Entering satisfied (uses satisfaction_eps):
            - Undercooled → Satisfied: temp <= (target - satisfaction_eps) while falling
            - Overcooled → Satisfied: temp >= (target + satisfaction_eps) while rising
            
            Exiting satisfied (uses opening/closing offsets - wider range):
            - Satisfied → Undercooled: temp > (target + opening_offset) while rising
            - Satisfied → Overcooled: temp < (target - closing_offset) while falling
            
        Note: Two-tier hysteresis - narrow eps range for entering satisfied,
              wider offset range for exiting satisfied (prevents flapping).
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

        Logic (two-tier hysteresis):
            - Entering satisfied: uses satisfaction_eps (narrower range)
              - From underheated: at target + eps while rising
              - From overheated: at target - eps while falling
            - Exiting satisfied: uses opening/closing offsets (wider range)
              - To underheated: below target - opening_offset
              - To overheated: above target + closing_offset
        """
        # Check if currently overheated (above exit upper bound)
        if current_temperature > self.satisfied_exit_upper:
            # If we're overheated, stay overheated until we reach entry lower bound while falling
            if current_state == "overheated":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_entry_lower
                ):
                    return "satisfied"
                return "overheated"
            # If satisfied and exceeding exit upper bound, become overheated
            if current_state == "satisfied":
                return "overheated"
            # Any other state -> overheated when exceeding exit upper bound
            return "overheated"

        # Check if currently underheated (below exit lower bound)
        if current_temperature < self.satisfied_exit_lower:
            # If we're underheated, stay underheated until we reach entry upper bound while rising
            if current_state == "underheated":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_upper
                ):
                    return "satisfied"
                return "underheated"
            # If satisfied and falling below exit lower bound, become underheated
            if current_state == "satisfied":
                return "underheated"
            # Any other state -> underheated when falling below exit lower bound
            return "underheated"

        # Between exit bounds - handle state-specific logic
        # If currently underheated, check for transition to satisfied
        if current_state == "underheated":
            # Must reach entry upper bound (target + eps) while rising to become satisfied
            if (
                temp_direction == "rising"
                and current_temperature >= self.satisfied_entry_upper
            ):
                return "satisfied"
            return "underheated"

        # If currently overheated, check for transition to satisfied
        if current_state == "overheated":
            # Must reach entry lower bound (target - eps) while falling to become satisfied
            if (
                temp_direction == "falling"
                and current_temperature <= self.satisfied_entry_lower
            ):
                return "satisfied"
            return "overheated"

        # If currently satisfied or unknown, stay/become satisfied (within exit bounds)
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

        Logic (two-tier hysteresis - inverted from heating):
            - Entering satisfied: uses satisfaction_eps (narrower range)
              - From undercooled: at target - eps while falling
              - From overcooled: at target + eps while rising
            - Exiting satisfied: uses opening/closing offsets (wider range)
              - To undercooled: above target + opening_offset
              - To overcooled: below target - closing_offset
        """
        # In cooling mode, opening_offset is added (not subtracted)
        # and closing_offset is subtracted (not added)
        exit_upper_cooling = self.target_temperature + self.opening_offset
        exit_lower_cooling = self.target_temperature - self.closing_offset
        
        # Check if currently undercooled (above exit upper bound - needs cooling)
        if current_temperature > exit_upper_cooling:
            # If we're undercooled, stay undercooled until we reach entry lower bound while falling
            if current_state == "undercooled":
                # Transition to satisfied only when reaching target - eps while falling
                if (
                    temp_direction == "falling"
                    and current_temperature <= self.satisfied_entry_lower
                ):
                    return "satisfied"
                return "undercooled"
            # If satisfied and exceeding exit upper bound, become undercooled
            if current_state == "satisfied":
                return "undercooled"
            # Any other state -> undercooled when exceeding exit upper bound
            return "undercooled"

        # Check if currently overcooled (below exit lower bound - too cool)
        if current_temperature < exit_lower_cooling:
            # If we're overcooled, stay overcooled until we reach entry upper bound while rising
            if current_state == "overcooled":
                # Transition to satisfied only when reaching target + eps while rising
                if (
                    temp_direction == "rising"
                    and current_temperature >= self.satisfied_entry_upper
                ):
                    return "satisfied"
                return "overcooled"
            # If satisfied and falling below exit lower bound, become overcooled
            if current_state == "satisfied":
                return "overcooled"
            # Any other state -> overcooled when falling below exit lower bound
            return "overcooled"

        # Between exit bounds - handle state-specific logic
        # If currently undercooled, check for transition to satisfied
        if current_state == "undercooled":
            # Must reach entry lower bound (target - eps) while falling to become satisfied
            if (
                temp_direction == "falling"
                and current_temperature <= self.satisfied_entry_lower
            ):
                return "satisfied"
            return "undercooled"

        # If currently overcooled, check for transition to satisfied
        if current_state == "overcooled":
            # Must reach entry upper bound (target + eps) while rising to become satisfied
            if (
                temp_direction == "rising"
                and current_temperature >= self.satisfied_entry_upper
            ):
                return "satisfied"
            return "overcooled"

        # If currently satisfied or unknown, stay/become satisfied (within exit bounds)
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
