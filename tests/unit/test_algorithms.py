"""Unit tests for core algorithms."""

from custom_components.multizone_climate.core.algorithms import (
    calculate_main_target_temperature,
    round_to_half_degree,
    clamp_temperature,
)


class TestCalculateMainTargetTemperature:
    """Test calculate_main_target_temperature function."""

    def test_slider_mode_basic(self):
        """
        Test slider-based calculation in heating mode.

        Scenario:
            - 2 zones: one underheated, one satisfied
            - Heating mode: should boost for underheated zone
            - Satisfied zone does not contribute to boost calculation (no deficit)
            - Expected: boost based on deficit
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 19.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 22.0,
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
        # Zone deficit = 1.0, capability = 0.0, boost = 1.0
        # New target = 20.0 + 1.0 = 21.0
        result = calculate_main_target_temperature(zones, config, 20.0, main_current_temp=20.0)
        assert result == 21.0

    def test_average_mode_basic(self):
        """
        Test average mode calculation in maintenance mode.

        Scenario:
            - 3 zones all satisfied
            - Average mode enabled
            - Expected: 22.0°C (average)
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 20.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 22.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "living",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 24.0,
                "satisfaction": "satisfied",
            },
        ]
        config = {
            "use_average_mode": True,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(zones, config, 20.0)
        assert result == 22.0

    def test_exclude_overheated_zones(self):
        """
        Test heating mode with one underheated zone (overheated zone excluded).

        Scenario:
            - 2 zones, one overheated
            - Should only consider underheated zone for boost calculation
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 19.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 25.0,
                "current_temperature": 26.0,
                "satisfaction": "overheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Deficit = 1.0, capability = 0.0, boost = 1.0
        # New target = 18.0 + 1.0 = 19.0
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 19.0

    def test_threshold_check(self):
        """
        Test threshold check prevents small updates.

        Scenario:
            - New target differs by 0.2°C
            - Threshold is 0.5°C
            - Expected: None (no update)
        """
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 21.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Current is 21.2, new would be 21.0, diff is 0.2 < 0.5
        result = calculate_main_target_temperature(zones, config, 21.2)
        assert result is None


class TestRoundToHalfDegree:
    """Test round_to_half_degree function."""

    def test_round_up(self):
        """Test rounding up: 22.3 -> 22.5"""
        assert round_to_half_degree(22.3) == 22.5

    def test_round_down(self):
        """Test rounding down: 22.2 -> 22.0"""
        assert round_to_half_degree(22.2) == 22.0


class TestClampTemperature:
    """Test clamp_temperature function."""

    def test_clamp_below_min(self):
        """Test clamping below minimum: 17.0 -> 18.0"""
        assert clamp_temperature(17.0, 18.0, 30.0) == 18.0

    def test_clamp_above_max(self):
        """Test clamping above maximum: 32.0 -> 30.0"""
        assert clamp_temperature(32.0, 18.0, 30.0) == 30.0

    def test_clamp_within_range(self):
        """Test that values within range are unchanged."""
        assert clamp_temperature(25.0, 18.0, 30.0) == 25.0


class TestCalculateMainTargetTemperatureEdgeCases:
    """Test edge cases for calculate_main_target_temperature."""

    def test_empty_zones_list(self):
        """Test with empty zones list."""
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature([], config, 20.0)
        assert result is None

    def test_all_zones_off(self):
        """Test with all zones off."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "false",
                "target_temperature": 20.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(zones, config, 20.0)
        assert result is None

    def test_all_zones_overheated(self):
        """Test with all zones overheated (idle mode)."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 21.0,
                "satisfaction": "overheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 23.0,
                "satisfaction": "overheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Idle mode - use minimum of overheated zones
        result = calculate_main_target_temperature(zones, config, 25.0)
        assert result == 20.0  # minimum of 20 and 22

    def test_single_zone_slider_mode(self):
        """Test with single underheated zone in slider mode."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 21.0,
                "current_temperature": 20.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Deficit = 1.0, capability = 0.0, boost = 1.0
        # New target = 18.0 + 1.0 = 19.0
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 19.0

    def test_slider_at_minimum(self):
        """Test slider at 0% (minimum) in heating mode."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 19.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 23.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.0,  # 0%
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Max deficit = 1.0, capability = 0.0, boost = 1.0
        # New target = 18.0 + 1.0 = 19.0
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 19.0

    def test_slider_at_maximum(self):
        """Test slider at 100% (maximum) in heating mode."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 18.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 20.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 1.0,  # 100%
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Max deficit = 4.0 (kitchen), capability = 0.0, boost = 4.0
        # New target = 18.0 + 4.0 = 22.0
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 22.0

    def test_clamping_to_limits(self):
        """Test that result is clamped to configured limits."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 35.0,  # Above max limit
                "current_temperature": 20.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Deficit = 15.0, capability = 0.0, boost = 15.0
        # New target = 18.0 + 15.0 = 33.0, clamped to 30.0
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 30.0  # clamped to max

    def test_rounding_behavior(self):
        """Test that rounding works correctly in heating mode."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.3,
                "current_temperature": 19.0,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 21.3,
                "current_temperature": 20.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": True,  # In heating mode this flag is ignored; algorithm uses max deficit
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        # Max deficit = 1.3, capability = 0.0, boost = 1.3
        # New target = 18.0 + 1.3 = 19.3, rounded to 19.5
        result = calculate_main_target_temperature(zones, config, 18.0, main_current_temp=18.0)
        assert result == 19.5

    def test_maintenance_mode_with_slider(self):
        """Test maintenance mode uses slider value when all zones satisfied."""
        zones = [
            {
                "id": "bedroom",
                "enabled": "true",
                "target_temperature": 20.0,
                "current_temperature": 20.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "kitchen",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 24.0,
                "satisfaction": "satisfied",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.75,  # 75% toward max
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(zones, config, 18.0)
        # 20 + 0.75 * (24 - 20) = 20 + 3 = 23.0
        assert result == 23.0


class TestDynamicHeatingBoost:
    """Test dynamic heating boost algorithm."""

    def test_heating_mode_single_underheated_zone(self):
        """
        Test dynamic boost with single underheated zone.

        Scenario:
            - Zone B: current=22.0°C, target=24.0°C → deficit = 2.0°C
            - Main: current=23.0°C, target=23.7°C → capability = 0.7°C
            - Required boost = 2.0 - 0.7 = 1.3°C
            - New main target = 23.7 + 1.3 = 25.0°C
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 22.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "zone_b",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 22.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=23.7, main_current_temp=23.0
        )
        assert result == 25.0  # 23.7 + 1.3 = 25.0

    def test_heating_mode_multiple_underheated_zones_uses_max_deficit(self):
        """
        Test that heating mode uses maximum deficit with multiple underheated zones.

        Scenario:
            - Zone A: current=20.0°C, target=21.0°C → deficit = 1.0°C
            - Zone B: current=19.0°C, target=22.0°C → deficit = 3.0°C (max)
            - Main: current=20.0°C, target=21.0°C → capability = 1.0°C
            - Required boost = 3.0 - 1.0 = 2.0°C
            - New main target = 21.0 + 2.0 = 23.0°C
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 21.0,
                "current_temperature": 20.0,
                "satisfaction": "underheated",
            },
            {
                "id": "zone_b",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 19.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=21.0, main_current_temp=20.0
        )
        assert result == 23.0  # 21.0 + 2.0 = 23.0

    def test_heating_mode_boost_reduces_as_zone_heats_up(self):
        """
        Test that boost automatically reduces as zone heats up.

        Scenario:
            - Zone B: current=23.0°C, target=24.0°C → deficit = 1.0°C
            - Main: current=23.5°C, target=24.5°C → capability = 1.0°C
            - Required boost = 1.0 - 1.0 = 0.0°C
            - New main target = 24.5 + 0.0 = 24.5°C (no additional boost needed)
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 22.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "zone_b",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 23.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=24.5, main_current_temp=23.5
        )
        # Change from 24.5 to 24.5 = 0, below threshold, so returns None
        assert result is None

    def test_maintenance_mode_all_zones_satisfied(self):
        """
        Test maintenance mode when all zones are satisfied.

        Scenario:
            - Zone A: 22.0/22.0 satisfied
            - Zone B: 24.0/24.0 satisfied
            - Slider at 50%
            - Expected: 23.0°C (midpoint, no boost)
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 22.0,
                "satisfaction": "satisfied",
            },
            {
                "id": "zone_b",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 24.0,
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
        result = calculate_main_target_temperature(
            zones, config, current_main_target=20.0, main_current_temp=20.0
        )
        assert result == 23.0  # midpoint between 22 and 24

    def test_heating_mode_clamped_to_max_limit(self):
        """
        Test that heating mode boost is clamped to max limit.

        Scenario:
            - Zone needs large boost that would exceed max_temp
            - Result should be clamped to 30.0°C
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 35.0,
                "current_temperature": 30.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=28.0, main_current_temp=27.0
        )
        assert result == 30.0  # clamped to max

    def test_heating_mode_without_main_current_temp(self):
        """
        Test heating mode when main_current_temp is not available.

        Scenario:
            - main_current_temp is None
            - Should assume capability = 0 and boost from current_main_target
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 24.0,
                "current_temperature": 22.0,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=23.0, main_current_temp=None
        )
        # Deficit = 2.0, capability = 0 (no main_current_temp), boost = 2.0
        # New target = 23.0 + 2.0 = 25.0
        assert result == 25.0

    def test_idle_mode_all_zones_overheated(self):
        """
        Test idle mode when all zones are overheated.

        Scenario:
            - All zones overheated (valves closed, system idle)
            - Should reduce main target to minimum zone target
        """
        zones = [
            {
                "id": "zone_a",
                "enabled": "true",
                "target_temperature": 22.0,
                "current_temperature": 24.0,
                "satisfaction": "overheated",
            },
            {
                "id": "zone_b",
                "enabled": "true",
                "target_temperature": 23.0,
                "current_temperature": 25.0,
                "satisfaction": "overheated",
            },
        ]
        config = {
            "use_average_mode": False,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(
            zones, config, current_main_target=25.0, main_current_temp=25.0
        )
        assert result == 22.0  # minimum of overheated zones
