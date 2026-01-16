"""Integration tests for climate platform."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from custom_components.multizone_climate.const import DOMAIN
from custom_components.multizone_climate.platforms.climate import (
    MainClimateDevice,
    ZoneClimateEntity,
)


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "main_climate": {
            "current_temperature": 21.0,
            "target_temperature": 22.0,
            "hvac_mode": "heat",
            "hvac_action": "heating",
        },
        "outdoor_temperature": 5.0,
        "multizone_enabled": True,
        "zones": {
            "zone_1": {
                "name": "Living Room",
                "current_temperature": 20.5,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "valve_state": "open",
                "temperature_rising": True,
                "temperature_falling": False,
                "priority": 1,
                "is_fallback": False,
            }
        },
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    client = AsyncMock()
    client.get_zone_state = AsyncMock(
        return_value={
            "current_temperature": 20.5,
            "target_temperature": 21.0,
            "satisfaction": "underheated",
            "temperature_rising": True,
            "temperature_falling": False,
        }
    )
    client.set_zone_state = AsyncMock()
    client.enqueue_job = AsyncMock()
    return client


class TestMainClimateDevice:
    """Test the main climate device entity."""

    async def test_main_climate_properties(
        self, hass: HomeAssistant, mock_coordinator
    ):
        """Test main climate device properties."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "main_climate_entity": "climate.main_hvac",
        }

        device = MainClimateDevice(
            coordinator=mock_coordinator,
            config_entry=config_entry,
        )

        # Test basic properties
        assert device.name == "Multizone Climate - Main"
        assert device.unique_id == "test_entry_main_climate"
        assert device.current_temperature == 21.0
        assert device.target_temperature == 22.0
        assert device.hvac_mode == HVACMode.HEAT
        assert device.hvac_action == HVACAction.HEATING

        # Test extra state attributes
        extra_attrs = device.extra_state_attributes
        assert extra_attrs["outdoor_temperature"] == 5.0
        assert extra_attrs["multizone_enabled"] is True

    async def test_main_climate_device_info(
        self, hass: HomeAssistant, mock_coordinator
    ):
        """Test main climate device info."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "main_climate_entity": "climate.main_hvac",
        }

        device = MainClimateDevice(
            coordinator=mock_coordinator,
            config_entry=config_entry,
        )

        device_info = device.device_info
        assert device_info["identifiers"] == {(DOMAIN, "multizone_climate_main")}
        assert device_info["name"] == "Multizone Climate"
        assert device_info["manufacturer"] == "Chester929"

    async def test_main_climate_hvac_modes(
        self, hass: HomeAssistant, mock_coordinator
    ):
        """Test HVAC mode mapping."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {"main_climate_entity": "climate.main_hvac"}

        device = MainClimateDevice(
            coordinator=mock_coordinator,
            config_entry=config_entry,
        )

        # Test heating mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "heat"
        assert device.hvac_mode == HVACMode.HEAT

        # Test cooling mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "cool"
        assert device.hvac_mode == HVACMode.COOL

        # Test off mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "off"
        assert device.hvac_mode == HVACMode.OFF

    async def test_main_climate_no_data(self, hass: HomeAssistant):
        """Test main climate when coordinator has no data."""
        coordinator = MagicMock()
        coordinator.data = None

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {"main_climate_entity": "climate.main_hvac"}

        device = MainClimateDevice(
            coordinator=coordinator,
            config_entry=config_entry,
        )

        assert device.current_temperature is None
        assert device.target_temperature is None
        assert device.hvac_mode == HVACMode.OFF
        assert device.hvac_action == HVACAction.OFF


class TestZoneClimateEntity:
    """Test the zone climate entity."""

    async def test_zone_climate_properties(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate entity properties."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states to return temperature sensor state
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        # Test basic properties
        assert entity.name == "Living Room"
        assert entity.unique_id == "test_entry_zone_zone_1"
        assert entity.current_temperature == 20.5
        assert entity.target_temperature_step == 0.1

    async def test_zone_climate_set_temperature(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test setting zone target temperature."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
        }

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        # Set temperature
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

        # Verify Redis was updated
        assert mock_redis_client.set_zone_state.called
        # Verify jobs were enqueued
        assert mock_redis_client.enqueue_job.call_count >= 2

    async def test_zone_climate_temperature_clamping(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test temperature clamping to min/max limits."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
        }

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        # Test clamping above max
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 35.0})
        call_args = mock_redis_client.set_zone_state.call_args
        assert call_args[0][1]["target_temperature"] == 30.0

        # Test clamping below min
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 10.0})
        call_args = mock_redis_client.set_zone_state.call_args
        assert call_args[0][1]["target_temperature"] == 18.0

    async def test_zone_climate_extra_state_attributes(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate extra state attributes."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        # Mock zone state in coordinator data
        coordinator_zone_data = {
            "satisfaction": "underheated",
            "valve_state": "open",
            "temperature_rising": True,
            "temperature_falling": False,
            "priority": 1,
            "is_fallback_valve": False,
        }
        mock_coordinator.data = {"zones": {"zone_1": coordinator_zone_data}}

        extra_attrs = entity.extra_state_attributes
        assert extra_attrs["satisfaction"] == "underheated"
        assert extra_attrs["valve_state"] == "open"
        assert extra_attrs["temperature_rising"] is True
        assert extra_attrs["temperature_falling"] is False
        assert extra_attrs["priority"] == 1
        assert extra_attrs["is_fallback_valve"] is False

    async def test_zone_climate_device_info(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate device info."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        device_info = entity.device_info
        assert device_info["identifiers"] == {(DOMAIN, "multizone_climate_main")}
        assert device_info["name"] == "Multizone Climate"

    async def test_zone_climate_no_temperature_sensor(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate when temperature sensor is unavailable."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states to return None (sensor unavailable)
        hass.states = MagicMock()
        hass.states.get.return_value = None

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        assert entity.current_temperature is None

    async def test_zone_climate_invalid_temperature(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate with invalid temperature reading."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states to return invalid temperature
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        assert entity.current_temperature is None

    async def test_zone_climate_update(
        self, hass: HomeAssistant, mock_coordinator, mock_redis_client
    ):
        """Test zone climate update method."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {}

        zone_config = {
            "zone_id": "zone_1",
            "name": "Living Room",
            "temp_sensor": "sensor.living_room_temp",
            "valve_switch": "switch.living_room_valve",
            "target_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "satisfaction_eps": 0.1,
            "priority": 1,
            "is_fallback": False,
        }

        # Mock hass.states
        mock_state = MagicMock()
        mock_state.state = "20.5"
        hass.states = MagicMock()
        hass.states.get.return_value = mock_state

        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            config_entry=config_entry,
            zone_config=zone_config,
            redis_client=mock_redis_client,
        )

        # Call update
        await entity.async_update()

        # Verify coordinator refresh was requested
        assert mock_coordinator.async_request_refresh.called
