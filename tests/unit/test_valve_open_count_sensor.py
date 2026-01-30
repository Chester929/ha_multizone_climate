"""Test valve open count sensor functionality."""

import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add custom_components path
multizone_climate_path = Path(__file__).parent.parent.parent / "multizone_climate"
sys.path.insert(0, str(multizone_climate_path))

from custom_components.multizone_climate.sensor import MultizoneTextSensor


@pytest.fixture
def mock_coordinator_with_backend_count():
    """Create a mock coordinator with backend-provided valve count."""
    coordinator = MagicMock()
    coordinator.data = {
        "open_valve_count": 3,  # Backend provides this count
        "zones": {
            "zone1": {"valve_state": "open"},
            "zone2": {"valve_state": "open"},
            "zone3": {"valve_state": "open"},
            "zone4": {"valve_state": "closed"},
        },
    }
    return coordinator


@pytest.fixture
def mock_coordinator_without_backend_count():
    """Create a mock coordinator without backend-provided valve count (fallback)."""
    coordinator = MagicMock()
    coordinator.data = {
        # No open_valve_count key - should fallback to calculation
        "zones": {
            "zone1": {"valve_state": "open"},
            "zone2": {"valve_state": "closed"},
            "zone3": {"valve_state": "open"},
        },
    }
    return coordinator


@pytest.fixture
def mock_coordinator_empty():
    """Create a mock coordinator with no data."""
    coordinator = MagicMock()
    coordinator.data = None
    return coordinator


def test_valve_count_uses_backend_value(mock_coordinator_with_backend_count):
    """Test that valve count sensor uses backend-provided value when available."""
    sensor = MultizoneTextSensor(mock_coordinator_with_backend_count, "open_valve_count")
    
    # Should use the backend value (3), not calculate from zones (which also happens to be 3)
    assert sensor.native_value == 3


def test_valve_count_fallback_calculation(mock_coordinator_without_backend_count):
    """Test that valve count sensor falls back to calculation when backend value not available."""
    sensor = MultizoneTextSensor(mock_coordinator_without_backend_count, "open_valve_count")
    
    # Should calculate from zones: 2 open valves
    assert sensor.native_value == 2


def test_valve_count_no_data(mock_coordinator_empty):
    """Test that valve count sensor returns None when coordinator has no data."""
    sensor = MultizoneTextSensor(mock_coordinator_empty, "open_valve_count")
    
    assert sensor.native_value is None


def test_valve_count_backend_zero():
    """Test that valve count correctly handles zero open valves from backend."""
    coordinator = MagicMock()
    coordinator.data = {
        "open_valve_count": 0,  # Backend says zero valves open
        "zones": {
            "zone1": {"valve_state": "closed"},
            "zone2": {"valve_state": "closed"},
        },
    }
    
    sensor = MultizoneTextSensor(coordinator, "open_valve_count")
    assert sensor.native_value == 0


def test_valve_count_all_valves_open():
    """Test valve count when all valves are open."""
    coordinator = MagicMock()
    coordinator.data = {
        "open_valve_count": 5,
        "zones": {
            f"zone{i}": {"valve_state": "open"} for i in range(1, 6)
        },
    }
    
    sensor = MultizoneTextSensor(coordinator, "open_valve_count")
    assert sensor.native_value == 5
