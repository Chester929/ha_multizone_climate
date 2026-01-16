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
    client = MagicMock()

    # Connection methods
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.ping = AsyncMock(return_value=True)

    # Configuration methods
    client.get_config = AsyncMock(
        return_value={
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
    )
    client.set_config = AsyncMock()
    client.update_config = AsyncMock()

    # Zone state methods
    client.get_zone_state = AsyncMock(return_value=None)
    client.set_zone_state = AsyncMock()
    client.get_zone_ids = AsyncMock(return_value=[])

    # Main climate methods
    client.get_main_climate_state = AsyncMock(return_value={})
    client.set_main_climate_state = AsyncMock()

    # Job queue methods
    client.enqueue_job = AsyncMock()
    client.dequeue_job = AsyncMock(return_value=None)
    client.get_queue_size = AsyncMock(return_value=0)

    # Job lock methods
    client.acquire_job_lock = AsyncMock(return_value=True)
    client.release_job_lock = AsyncMock()
    client.is_job_locked = AsyncMock(return_value=False)

    # Valve lock methods
    client.set_valve_lock = AsyncMock()
    client.is_valve_locked = AsyncMock(return_value=False)
    client.get_valve_lock = AsyncMock(return_value=None)

    # Job status methods
    client.set_job_status = AsyncMock()
    client.get_job_status = AsyncMock(return_value=None)

    return client


@pytest.fixture
def mock_hass():
    """
    Mock Home Assistant instance.

    Returns:
        MagicMock: Mock hass instance
    """
    hass = MagicMock()

    # Services
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.services.call = MagicMock()

    # States
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.states.async_set = AsyncMock()
    hass.states.set = MagicMock()

    # Events
    hass.bus = MagicMock()
    hass.bus.async_fire = AsyncMock()
    hass.bus.fire = MagicMock()
    hass.bus.async_listen = MagicMock()

    # Data
    hass.data = {}

    # Config
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"

    # Helper methods
    hass.async_add_executor_job = AsyncMock()
    hass.async_create_task = MagicMock()

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
