"""Unit tests for the actual climate.py MultizoneClimateEntity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_TEMPERATURE

from custom_components.multizone_climate.climate import MultizoneClimateEntity


class TestMultizoneClimateEntity:
    """Test the actual MultizoneClimateEntity that uses backend API."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.backend_url = "http://localhost:8080"
        coordinator.session = MagicMock()
        coordinator.push_state_update = AsyncMock()
        return coordinator

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.states = MagicMock()
        # Mock temperature sensor
        sensor_state = MagicMock()
        sensor_state.state = "20.5"
        hass.states.get = MagicMock(return_value=sensor_state)
        hass.async_create_task = MagicMock()
        return hass

    def test_entity_initialization(self, mock_coordinator):
        """Test entity initializes with correct properties."""
        entity = MultizoneClimateEntity(
            coordinator=mock_coordinator,
            zone_id="bedroom",
            zone_name="Bedroom",
            temperature_sensor="sensor.bedroom_temp",
            valve_switch="switch.bedroom_valve",
            target_temp=21.0,
            opening_offset=0.5,
            closing_offset=0.5,
            priority=50,
            is_fallback=False,
        )

        assert entity.name == "Bedroom"
        assert entity.target_temperature == 21.0
        assert entity.hvac_mode == HVACMode.HEAT
        assert entity._zone_id == "bedroom"

    async def test_set_temperature(self, mock_coordinator, mock_hass):
        """Test setting target temperature pushes to backend."""
        # Mock the HTTP session post
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_coordinator.session.post = MagicMock(return_value=mock_response)

        entity = MultizoneClimateEntity(
            coordinator=mock_coordinator,
            zone_id="bedroom",
            zone_name="Bedroom",
            temperature_sensor="sensor.bedroom_temp",
            valve_switch="switch.bedroom_valve",
            target_temp=20.0,
            opening_offset=0.5,
            closing_offset=0.5,
            priority=50,
            is_fallback=False,
        )
        entity.hass = mock_hass

        # Mock async_write_ha_state to avoid threading issues in tests
        with patch.object(entity, "async_write_ha_state"):
            # Set new temperature
            await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

        # Verify temperature was updated locally
        assert entity.target_temperature == 22.0

        # Verify backend API was called
        mock_coordinator.session.post.assert_called_once()
        call_args = mock_coordinator.session.post.call_args
        assert "/api/integration/state_update" in call_args[0][0]

    async def test_set_hvac_mode(self, mock_coordinator, mock_hass):
        """Test setting HVAC mode."""
        entity = MultizoneClimateEntity(
            coordinator=mock_coordinator,
            zone_id="bedroom",
            zone_name="Bedroom",
            temperature_sensor="sensor.bedroom_temp",
            valve_switch="switch.bedroom_valve",
            target_temp=20.0,
            opening_offset=0.5,
            closing_offset=0.5,
            priority=50,
            is_fallback=False,
        )
        entity.hass = mock_hass

        # Mock async_write_ha_state to avoid threading issues in tests
        with patch.object(entity, "async_write_ha_state"):
            # Test setting to OFF
            await entity.async_set_hvac_mode(HVACMode.OFF)
            assert entity.hvac_mode == HVACMode.OFF

            # Test setting to HEAT
            await entity.async_set_hvac_mode(HVACMode.HEAT)
            assert entity.hvac_mode == HVACMode.HEAT

    def test_extra_state_attributes(self, mock_coordinator):
        """Test extra state attributes include zone configuration."""
        entity = MultizoneClimateEntity(
            coordinator=mock_coordinator,
            zone_id="bedroom",
            zone_name="Bedroom",
            temperature_sensor="sensor.bedroom_temp",
            valve_switch="switch.bedroom_valve",
            target_temp=20.0,
            opening_offset=0.5,
            closing_offset=0.3,
            priority=75,
            is_fallback=True,
        )

        attrs = entity.extra_state_attributes

        assert attrs["zone_id"] == "bedroom"
        assert attrs["temperature_sensor"] == "sensor.bedroom_temp"
        assert attrs["valve_switch"] == "switch.bedroom_valve"
        assert attrs["opening_offset"] == 0.5
        assert attrs["closing_offset"] == 0.3
        assert attrs["priority"] == 75
        assert attrs["is_fallback_valve"] is True
