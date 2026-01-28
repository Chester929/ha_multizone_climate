"""Test sensor handling of missing temperature values."""

import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add custom_components path
multizone_climate_path = Path(__file__).parent.parent.parent / "multizone_climate"
sys.path.insert(0, str(multizone_climate_path))

from custom_components.multizone_climate.sensor import (
    ZoneTemperatureSensor,
    MultizoneTemperatureSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "main_climate": {
            # current_temperature is missing (not set at all)
            "target_temperature": 20.0,
            "outdoor_temperature": None,  # explicitly None
        },
        "zones": {
            "zone1": {
                # current_temperature is missing (not set at all)
                "target_temperature": "22",
            },
            "zone2": {
                "current_temperature": 21.5,
                "target_temperature": 22.0,
            },
            "zone3": {
                "current_temperature": None,  # explicitly None
                "target_temperature": 20.0,
            },
        },
    }

    def get_zone_data(zone_id):
        return coordinator.data.get("zones", {}).get(zone_id)

    coordinator.get_zone_data = get_zone_data
    return coordinator


def test_zone_temperature_sensor_missing_value(mock_coordinator):
    """Test that ZoneTemperatureSensor returns None for missing values."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone1", "Zone 1", "current_temperature"
    )

    # Should return None when key is not in data
    assert sensor.native_value is None


def test_zone_temperature_sensor_none_value(mock_coordinator):
    """Test that ZoneTemperatureSensor returns None for None values."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone3", "Zone 3", "current_temperature"
    )

    # Should return None
    assert sensor.native_value is None


def test_zone_temperature_sensor_numeric_string(mock_coordinator):
    """Test that ZoneTemperatureSensor does NOT parse numeric strings."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone1", "Zone 1", "target_temperature"
    )

    # String values should return None (backend should send numbers)
    assert sensor.native_value is None


def test_zone_temperature_sensor_float_value(mock_coordinator):
    """Test that ZoneTemperatureSensor handles float values."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone2", "Zone 2", "current_temperature"
    )

    # Should return float value
    assert sensor.native_value == 21.5


def test_multizone_temperature_sensor_missing_value(mock_coordinator):
    """Test that MultizoneTemperatureSensor returns None for missing values."""
    sensor = MultizoneTemperatureSensor(
        mock_coordinator, "main_current_temperature"
    )

    # Should return None when key is not in data
    assert sensor.native_value is None


def test_multizone_temperature_sensor_none_value(mock_coordinator):
    """Test that MultizoneTemperatureSensor returns None for None values."""
    sensor = MultizoneTemperatureSensor(
        mock_coordinator, "outdoor_temperature"
    )

    # Should return None
    assert sensor.native_value is None


def test_multizone_temperature_sensor_valid_value(mock_coordinator):
    """Test that MultizoneTemperatureSensor handles valid float values."""
    sensor = MultizoneTemperatureSensor(
        mock_coordinator, "main_target_temperature"
    )

    # Should return float value
    assert sensor.native_value == 20.0
