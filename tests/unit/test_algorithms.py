"""Unit tests for core algorithms."""
import pytest
from custom_components.multizone_climate.core.algorithms import (
    calculate_main_target_temperature,
    round_to_half_degree,
    clamp_temperature,
)


class TestCalculateMainTargetTemperature:
    """Test calculate_main_target_temperature function."""

    def test_slider_mode_basic(self):
        """
        Test slider-based calculation.
        
        Scenario:
            - 2 zones with targets 20°C and 22°C
            - Slider at 50%
            - Expected: 21.0°C (midpoint)
        """
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
        result = calculate_main_target_temperature(zones, config, 20.0)
        assert result == 21.0

    def test_average_mode_basic(self):
        """
        Test average mode calculation.
        
        Scenario:
            - 3 zones with targets 20°C, 22°C, 24°C
            - Average mode enabled
            - Expected: 22.0°C (average)
        """
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
            {
                "id": "living",
                "state": "ON",
                "target_temperature": 24.0,
                "satisfaction": "underheated",
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
        Test that overheated zones are excluded.
        
        Scenario:
            - 2 zones, one overheated
            - Should only consider non-overheated zone
        """
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
                "target_temperature": 25.0,
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
        # Should only use bedroom (20.0), kitchen is overheated
        result = calculate_main_target_temperature(zones, config, 18.0)
        assert result == 20.0

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
                "state": "ON",
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
                "state": "OFF",
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
        """Test with all zones overheated (uses all active zones as fallback)."""
        zones = [
            {
                "id": "bedroom",
                "state": "ON",
                "target_temperature": 20.0,
                "satisfaction": "overheated",
            },
            {
                "id": "kitchen",
                "state": "ON",
                "target_temperature": 22.0,
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
        # Should use all zones as fallback
        result = calculate_main_target_temperature(zones, config, 18.0)
        assert result == 21.0  # midpoint of 20 and 22

    def test_single_zone_slider_mode(self):
        """Test with single zone in slider mode."""
        zones = [
            {
                "id": "bedroom",
                "state": "ON",
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
        result = calculate_main_target_temperature(zones, config, 18.0)
        # With single zone, min == max, so result should be that temperature
        assert result == 21.0

    def test_slider_at_minimum(self):
        """Test slider at 0% (minimum)."""
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
                "target_temperature": 24.0,
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
        result = calculate_main_target_temperature(zones, config, 18.0)
        assert result == 20.0  # minimum zone target

    def test_slider_at_maximum(self):
        """Test slider at 100% (maximum)."""
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
                "target_temperature": 24.0,
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
        result = calculate_main_target_temperature(zones, config, 18.0)
        assert result == 24.0  # maximum zone target

    def test_clamping_to_limits(self):
        """Test that result is clamped to configured limits."""
        zones = [
            {
                "id": "bedroom",
                "state": "ON",
                "target_temperature": 35.0,  # Above max limit
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
        result = calculate_main_target_temperature(zones, config, 18.0)
        assert result == 30.0  # clamped to max

    def test_rounding_behavior(self):
        """Test that rounding works correctly."""
        zones = [
            {
                "id": "bedroom",
                "state": "ON",
                "target_temperature": 20.3,
                "satisfaction": "underheated",
            },
            {
                "id": "kitchen",
                "state": "ON",
                "target_temperature": 21.3,
                "satisfaction": "underheated",
            },
        ]
        config = {
            "use_average_mode": True,  # Average of 20.3 and 21.3 = 20.8
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        result = calculate_main_target_temperature(zones, config, 18.0)
        # 20.8 should round to 21.0
        assert result == 21.0
