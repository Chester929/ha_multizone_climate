"""Unit tests for satisfaction state machine."""

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
            - Should stay satisfied within offset bounds (exit bounds)
            - Two-tier hysteresis: narrow eps for entering, wide offsets for exiting
        """
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Start satisfied at 21.0
        state = "satisfied"

        # Temperature drops to 20.8 (above exit lower bound 20.7, below entry lower bound 20.9)
        # Should stay satisfied because we use wider offset bounds for exiting
        state, direction = state_machine.update_state(
            current_temperature=20.8,
            previous_temperature=21.0,
            current_state=state,
            hvac_mode="heating",
        )
        assert state == "satisfied"  # Should stay satisfied (within offset exit bounds)

        # Temperature rises to 21.2 (below exit upper bound 21.3, above entry upper bound 21.1)
        # Should stay satisfied because we use wider offset bounds for exiting
        state, direction = state_machine.update_state(
            current_temperature=21.2,
            previous_temperature=20.8,
            current_state=state,
            hvac_mode="heating",
        )
        assert state == "satisfied"  # Should stay satisfied (within offset exit bounds)

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

    def test_heating_unknown_to_underheated(self):
        """Test transition from unknown to underheated in heating mode."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Temperature at 20.0 (below lower bound 20.7)
        new_state, direction = state_machine.update_state(
            current_temperature=20.0,
            previous_temperature=20.1,
            current_state="unknown",
            hvac_mode="heating",
        )

        assert new_state == "underheated"
        assert direction == "falling"

    def test_heating_overheated_to_satisfied(self):
        """Test transition from overheated to satisfied in heating mode."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Temperature falling from 22.0 to 20.9 (below target - eps)
        new_state, direction = state_machine.update_state(
            current_temperature=20.9,
            previous_temperature=22.0,
            current_state="overheated",
            hvac_mode="heating",
        )

        assert new_state == "satisfied"
        assert direction == "falling"

    def test_cooling_overcooled_to_satisfied(self):
        """Test transition from overcooled to satisfied in cooling mode."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=23.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Temperature at 22.0 (below lower bound 22.7) - overcooled
        # Temperature rising to 23.1 (above target + eps)
        new_state, direction = state_machine.update_state(
            current_temperature=23.1,
            previous_temperature=22.0,
            current_state="overcooled",
            hvac_mode="cooling",
        )

        assert new_state == "satisfied"
        assert direction == "rising"

    def test_hvac_off_returns_unknown(self):
        """Test that HVAC off mode returns unknown state."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        new_state, direction = state_machine.update_state(
            current_temperature=21.0,
            previous_temperature=20.5,
            current_state="satisfied",
            hvac_mode="off",
        )

        assert new_state == "unknown"

    def test_stable_temperature(self):
        """Test stable temperature direction."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=21.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Same temperature
        new_state, direction = state_machine.update_state(
            current_temperature=21.0,
            previous_temperature=21.0,
            current_state="satisfied",
            hvac_mode="heating",
        )

        assert direction == "stable"

    def test_cooling_satisfied_to_overcooled(self):
        """Test transition from satisfied to overcooled in cooling mode."""
        state_machine = ZoneSatisfactionStateMachine(
            target_temperature=23.0,
            opening_offset=0.3,
            closing_offset=0.3,
            satisfaction_eps=0.1,
        )

        # Temperature falling from 23.0 to 22.6 (below lower bound 22.7)
        new_state, direction = state_machine.update_state(
            current_temperature=22.6,
            previous_temperature=23.0,
            current_state="satisfied",
            hvac_mode="cooling",
        )

        assert new_state == "overcooled"
        assert direction == "falling"
