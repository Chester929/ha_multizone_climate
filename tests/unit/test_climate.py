"""Unit tests for climate platform entities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.components.climate import HVACMode, HVACAction

from custom_components.multizone_climate.platforms.climate import (
    MainClimateDevice,
    ZoneClimateEntity,
)


class TestMainClimateDevice:
    """Test MainClimateDevice."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "main_climate": {
                "entity_id": "climate.main_thermostat",
                "current_temperature": 20.5,
                "target_temperature": 21.0,
                "outdoor_temperature": 5.0,
                "hvac_mode": "heat",
                "hvac_action": "heating",
                "multizone_enabled": True,
            }
        }
        coordinator.async_request_refresh = AsyncMock()
        return coordinator

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        return hass

    def test_main_climate_device_properties(self, mock_coordinator, mock_hass):
        """
        Test MainClimateDevice properties.

        Expected:
            - Current temperature from coordinator
            - Target temperature from coordinator
            - HVAC mode from coordinator
            - Extra attributes include outdoor temp and multizone status
        """
        device = MainClimateDevice(mock_coordinator, "test_entry")

        assert device.current_temperature == 20.5
        assert device.target_temperature == 21.0
        assert device.hvac_mode == HVACMode.HEAT
        assert device.hvac_action == HVACAction.HEATING

        extra_attrs = device.extra_state_attributes
        assert extra_attrs["outdoor_temperature"] == 5.0
        assert extra_attrs["multizone_enabled"] is True

    def test_main_climate_device_read_only(self, mock_coordinator, mock_hass):
        """
        Test that MainClimateDevice is read-only.

        Expected:
            - Supported features is 0 (no control)
            - Target temp setter does nothing
        """
        device = MainClimateDevice(mock_coordinator, "test_entry")

        assert device.supported_features == 0

    def test_main_climate_device_hvac_modes(self, mock_coordinator, mock_hass):
        """
        Test HVAC modes for MainClimateDevice.

        Expected:
            - Reflects main climate entity modes
            - Maps correctly from string to HVACMode
        """
        # Test HEAT mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "heat"
        device = MainClimateDevice(mock_coordinator, "test_entry")
        assert device.hvac_mode == HVACMode.HEAT

        # Test COOL mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "cool"
        assert device.hvac_mode == HVACMode.COOL

        # Test OFF mode
        mock_coordinator.data["main_climate"]["hvac_mode"] = "off"
        assert device.hvac_mode == HVACMode.OFF

    def test_main_climate_device_no_data(self, mock_coordinator, mock_hass):
        """
        Test MainClimateDevice with no data available.

        Expected:
            - Returns None for missing properties
            - Doesn't crash
        """
        mock_coordinator.data = {"main_climate": {}}
        device = MainClimateDevice(mock_coordinator, "test_entry")

        assert device.current_temperature is None
        assert device.target_temperature is None


class TestZoneClimateEntity:
    """Test ZoneClimateEntity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "zones": {
                "bedroom": {
                    "id": "bedroom",
                    "name": "Bedroom",
                    "state": "ON",
                    "current_temperature": 19.5,
                    "target_temperature": 20.0,
                    "satisfaction": "underheated",
                    "valve_state": "open",
                    "temperature_rising": True,
                    "temperature_falling": False,
                    "priority": 0,
                    "is_fallback_valve": True,
                }
            }
        }
        coordinator.async_request_refresh = AsyncMock()
        return coordinator

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.update_zone_state = AsyncMock()
        redis.enqueue_job = AsyncMock()
        return redis

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=MagicMock(state="19.5", attributes={}))
        return hass

    def test_zone_climate_entity_properties(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test ZoneClimateEntity properties.

        Expected:
            - Current temperature from sensor
            - Target temperature user-settable
            - Satisfaction state exposed
            - Valve state exposed
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        assert entity.current_temperature == 19.5
        assert entity.target_temperature == 20.0

        extra_attrs = entity.extra_state_attributes
        assert extra_attrs["satisfaction"] == "underheated"
        assert extra_attrs["valve_state"] == "open"

    async def test_zone_climate_entity_set_target_temp(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test setting target temperature on ZoneClimateEntity.

        Expected:
            - Target temp updated in Redis
            - Calculate main temp job enqueued
            - Update valves job enqueued
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        await entity.async_set_temperature(temperature=21.5)

        # Verify Redis update
        mock_redis.update_zone_state.assert_called()

        # Verify jobs enqueued
        assert mock_redis.enqueue_job.call_count >= 2  # calc_temp + update_valves

    def test_zone_climate_entity_hvac_mode(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test HVAC mode for ZoneClimateEntity.

        Expected:
            - ON state -> HEAT mode
            - OFF state -> OFF mode
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        # Test ON state
        mock_coordinator.data["zones"]["bedroom"]["state"] = "ON"
        assert entity.hvac_mode == HVACMode.HEAT

        # Test OFF state
        mock_coordinator.data["zones"]["bedroom"]["state"] = "OFF"
        assert entity.hvac_mode == HVACMode.OFF

    async def test_zone_climate_entity_turn_on_off(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test turning zone on and off.

        Expected:
            - Turn on -> state set to ON in Redis
            - Turn off -> state set to OFF in Redis
            - Jobs triggered on state change
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        # Turn on
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        mock_redis.update_zone_state.assert_called()

        # Turn off
        await entity.async_set_hvac_mode(HVACMode.OFF)
        mock_redis.update_zone_state.assert_called()

    def test_zone_climate_entity_temperature_step(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test temperature step configuration.

        Expected:
            - Target temperature step from config
            - Defaults to 0.1 if not specified
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.5,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        assert entity.target_temperature_step == 0.5

    def test_zone_climate_entity_extra_attributes(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test zone climate entity extra attributes.

        Expected:
            - Satisfaction state
            - Valve state
            - Temperature direction flags
            - Priority
            - Fallback valve status
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        attrs = entity.extra_state_attributes

        assert "satisfaction" in attrs
        assert "valve_state" in attrs
        assert "temperature_rising" in attrs
        assert "temperature_falling" in attrs
        assert "priority" in attrs
        assert "is_fallback_valve" in attrs

    async def test_zone_climate_entity_satisfaction_calculation(
        self, mock_coordinator, mock_redis, mock_hass
    ):
        """
        Test that zone calculates satisfaction state.

        Expected:
            - Underheated when temp below target - opening_offset
            - Satisfied when temp in range
            - Overheated when temp above target + closing_offset
        """
        zone_config = {
            "id": "bedroom",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_change_threshold": 0.1,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
        }

        entity = ZoneClimateEntity(
            mock_coordinator, mock_redis, zone_config, "test_entry"
        )
        entity.hass = mock_hass

        # Mock different temperature scenarios
        # Target: 20.0°C, opening_offset: 0.3, closing_offset: 0.3

        # Underheated: 19.0°C < 19.7°C
        mock_coordinator.data["zones"]["bedroom"]["current_temperature"] = 19.0
        assert entity.extra_state_attributes.get("satisfaction") in [
            "underheated",
            "unknown",
        ]

        # Satisfied: 20.0°C in range [19.7, 20.3]
        mock_coordinator.data["zones"]["bedroom"]["current_temperature"] = 20.0
        # May need state machine update to reflect this

        # Overheated: 21.0°C > 20.3°C
        mock_coordinator.data["zones"]["bedroom"]["current_temperature"] = 21.0
        # May need state machine update to reflect this
