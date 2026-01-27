"""Test sensor handling of N/A values."""

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
            "current_temperature": "N/A",
            "target_temperature": 20.0,
            "outdoor_temperature": None,
        },
        "zones": {
            "zone1": {
                "current_temperature": "N/A",
                "target_temperature": "22",
            },
            "zone2": {
                "current_temperature": 21.5,
                "target_temperature": 22.0,
            },
        },
    }
    
    def get_zone_data(zone_id):
        return coordinator.data.get("zones", {}).get(zone_id)
    
    coordinator.get_zone_data = get_zone_data
    return coordinator


def test_zone_temperature_sensor_na_value(mock_coordinator):
    """Test that ZoneTemperatureSensor returns None for N/A values."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone1", "Zone 1", "current_temperature"
    )
    
    # Should return None for "N/A" string
    assert sensor.native_value is None


def test_zone_temperature_sensor_none_value(mock_coordinator):
    """Test that ZoneTemperatureSensor returns None for None values."""
    # Update mock data to have None
    mock_coordinator.data["zones"]["zone1"]["current_temperature"] = None
    
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone1", "Zone 1", "current_temperature"
    )
    
    # Should return None
    assert sensor.native_value is None


def test_zone_temperature_sensor_numeric_string(mock_coordinator):
    """Test that ZoneTemperatureSensor parses numeric strings."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone1", "Zone 1", "target_temperature"
    )
    
    # Should parse "22" to 22.0
    assert sensor.native_value == 22.0


def test_zone_temperature_sensor_float_value(mock_coordinator):
    """Test that ZoneTemperatureSensor handles float values."""
    sensor = ZoneTemperatureSensor(
        mock_coordinator, "zone2", "Zone 2", "current_temperature"
    )
    
    # Should return float value
    assert sensor.native_value == 21.5


def test_multizone_temperature_sensor_na_value(mock_coordinator):
    """Test that MultizoneTemperatureSensor returns None for N/A values."""
    sensor = MultizoneTemperatureSensor(
        mock_coordinator, "main_current_temperature"
    )
    
    # Should return None for "N/A" string
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
