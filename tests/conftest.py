"""Test fixtures for Multizone Climate integration."""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_redis_client():
    """
    Mock Redis client for testing.
    
    Returns:
        MagicMock: Mock Redis client with async methods
    """
    # TODO: Create mock Redis client
    # TODO: Mock all methods used in tests
    # TODO: Set up default return values
    client = MagicMock()
    client.connect = AsyncMock()
    client.get_config = AsyncMock(return_value={})
    client.get_zone_state = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_hass():
    """
    Mock Home Assistant instance.
    
    Returns:
        MagicMock: Mock hass instance
    """
    # TODO: Create mock hass
    # TODO: Mock services, states, events
    hass = MagicMock()
    hass.services = MagicMock()
    hass.states = MagicMock()
    return hass


@pytest.fixture
def sample_config():
    """
    Sample configuration for testing.
    
    Returns:
        dict: Sample configuration
    """
    return {
        "main_climate_entity_id": "climate.main_thermostat",
        "use_average_mode": False,
        "main_target_all_zones_satisfied": 0.5,
        "min_valves_open": 1,
        "main_min_temp": 18.0,
        "main_max_temp": 30.0,
        "main_change_threshold": 0.5,
        "valve_actuation_delay": 120,
        "satisfaction_eps": 0.0,
    }


@pytest.fixture
def sample_zones():
    """
    Sample zones for testing.
    
    Returns:
        list: Sample zone configurations
    """
    return [
        {
            "id": "bedroom",
            "name": "Bedroom",
            "state": "ON",
            "target_temperature": 20.0,
            "current_temperature": 19.0,
            "satisfaction": "underheated",
            "valve_id": "switch.bedroom_valve",
            "valve_state": "open",
            "priority": 0,
            "is_fallback_valve": True,
        },
        {
            "id": "kitchen",
            "name": "Kitchen",
            "state": "ON",
            "target_temperature": 22.0,
            "current_temperature": 21.5,
            "satisfaction": "satisfied",
            "valve_id": "switch.kitchen_valve",
            "valve_state": "open",
            "priority": 0,
            "is_fallback_valve": False,
        },
    ]
