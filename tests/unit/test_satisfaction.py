"""Unit tests for satisfaction state machine."""
import pytest
from custom_components.multizone_climate.core.satisfaction import (
    ZoneSatisfactionStateMachine,
)


class TestZoneSatisfactionStateMachine:
    """Test zone satisfaction state machine."""

    def test_underheated_to_satisfied_heating(self):
        """
        Test transition from underheated to satisfied in heating mode.
        
        Scenario:
            - Target: 21.0°C, eps: 0.1°C
            - Current: 21.1°C (rising from underheated)
            - Expected: satisfied
        """
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )
        
        # Temperature rising from 20.5 to 21.1
        new_state, direction = state_machine.update_state(
            current_temperature=21.1,
            previous_temperature=20.5,
            current_state="underheated",
            hvac_mode="heating",
        )
        
        assert new_state == "satisfied"
        assert direction == "rising"

    def test_satisfied_to_overheated_heating(self):
        """
        Test transition from satisfied to overheated in heating mode.
        
        Scenario:
            - Target: 21.0°C, closing_offset: 0.3°C
            - Current: 21.4°C (rising from satisfied)
            - Expected: overheated
        """
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )
        
        # Temperature rising from 21.2 to 21.4 (above upper bound 21.3)
        new_state, direction = state_machine.update_state(
            current_temperature=21.4,
            previous_temperature=21.2,
            current_state="satisfied",
            hvac_mode="heating",
        )
        
        assert new_state == "overheated"
        assert direction == "rising"

    def test_hysteresis_prevents_flapping(self):
        """
        Test that hysteresis prevents rapid state changes.
        
        Scenario:
            - Temperature oscillating around target
            - Should stay satisfied within bounds
        """
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )
        
        # Start satisfied at 21.0
        state = "satisfied"
        
        # Temperature drops to 20.8 (still above lower bound 20.7)
        state, direction = state_machine.update_state(
            current_temperature=20.8,
            previous_temperature=21.0,
            current_state=state,
            hvac_mode="heating",
        )
        assert state == "satisfied"  # Should stay satisfied
        
        # Temperature rises to 21.2 (still below upper bound 21.3)
        state, direction = state_machine.update_state(
            current_temperature=21.2,
            previous_temperature=20.8,
            current_state=state,
            hvac_mode="heating",
        )
        assert state == "satisfied"  # Should stay satisfied

    def test_cooling_mode_inverted(self):
        """
        Test that cooling mode logic is inverted.
        
        Scenario:
            - Cooling mode with temp above target
            - Expected: undercooled (needs cooling)
        """
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=23.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )
        
        # Temperature at 24.0 (above upper bound 23.3)
        # In cooling mode, this means undercooled (needs cooling)
        new_state, direction = state_machine.update_state(
            current_temperature=24.0,
            previous_temperature=24.5,
            current_state="undercooled",
            hvac_mode="cooling",
        )
        
        assert new_state == "undercooled"
        assert direction == "falling"
        
        # Temperature falls to 22.9 (below target - eps)
        # Should become satisfied
        new_state, direction = state_machine.update_state(
            current_temperature=22.9,
            previous_temperature=24.0,
            current_state="undercooled",
            hvac_mode="cooling",
        )
        
        assert new_state == "satisfied"
        assert direction == "falling"
