"""Unit tests for outdoor temperature sensor configuration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.multizone_climate.config_flow import (
    MultizoneClimateConfigFlow,
    MultizoneClimateOptionsFlow,
)


class TestOutdoorTemperatureSensorConfig:
    """Test the outdoor temperature sensor configuration."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.states = MagicMock()
        # By default, all entities exist
        hass.states.get = MagicMock(return_value=MagicMock())
        hass.data = {}
        return hass

    @pytest.fixture
    def config_flow(self, mock_hass):
        """Create config flow instance."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = mock_hass
        return flow

    @pytest.mark.asyncio
    async def test_outdoor_sensor_optional(self, config_flow, mock_hass):
        """Test that outdoor temperature sensor is optional."""
        # Setup: main climate exists
        user_input = {
            "main_climate_entity": "climate.main",
            # No outdoor_temperature_sensor provided
        }

        result = await config_flow.async_step_user(user_input)

        # Should proceed to zone_initial step
        assert result["type"] == "form"
        assert result["step_id"] == "zone_initial"

    @pytest.mark.asyncio
    async def test_outdoor_sensor_validation(self, config_flow, mock_hass):
        """Test that outdoor temperature sensor is validated if provided."""
        # Setup: main climate exists, outdoor sensor does not
        def mock_get_state(entity_id):
            if entity_id == "climate.main":
                return MagicMock()
            if entity_id == "sensor.outdoor_temp":
                return None  # Entity doesn't exist
            return MagicMock()

        mock_hass.states.get = mock_get_state

        user_input = {
            "main_climate_entity": "climate.main",
            "outdoor_temperature_sensor": "sensor.outdoor_temp",
        }

        result = await config_flow.async_step_user(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "errors" in result
        assert result["errors"]["outdoor_temperature_sensor"] == "entity_not_found"

    @pytest.mark.asyncio
    async def test_outdoor_sensor_valid(self, config_flow, mock_hass):
        """Test that valid outdoor temperature sensor is accepted."""
        # Setup: both entities exist
        user_input = {
            "main_climate_entity": "climate.main",
            "outdoor_temperature_sensor": "sensor.outdoor_temp",
        }

        result = await config_flow.async_step_user(user_input)

        # Should proceed to zone_initial step
        assert result["type"] == "form"
        assert result["step_id"] == "zone_initial"
        # Data should be stored
        assert config_flow.data == user_input


class TestOutdoorTemperatureSensorOptions:
    """Test the outdoor temperature sensor options flow."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {
            "main_climate_entity": "climate.main",
            "outdoor_temperature_sensor": "sensor.outdoor_temp",
        }
        return entry

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=MagicMock())
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        return hass

    @pytest.fixture
    def options_flow(self, mock_config_entry, mock_hass):
        """Create options flow instance."""
        flow = MultizoneClimateOptionsFlow(mock_config_entry)
        flow.hass = mock_hass
        return flow

    @pytest.mark.asyncio
    async def test_edit_outdoor_sensor_validation(self, options_flow, mock_hass):
        """Test that outdoor sensor is validated when editing."""
        # Setup: new outdoor sensor doesn't exist
        def mock_get_state(entity_id):
            if entity_id == "climate.main":
                return MagicMock()
            if entity_id == "sensor.new_outdoor":
                return None  # Entity doesn't exist
            return MagicMock()

        mock_hass.states.get = mock_get_state

        user_input = {
            "main_climate_entity": "climate.main",
            "outdoor_temperature_sensor": "sensor.new_outdoor",
        }

        result = await options_flow.async_step_edit_main(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert result["step_id"] == "edit_main"
        assert "errors" in result
        assert result["errors"]["outdoor_temperature_sensor"] == "entity_not_found"

    @pytest.mark.asyncio
    async def test_edit_outdoor_sensor_remove(self, options_flow, mock_hass):
        """Test that outdoor sensor can be removed (set to None)."""
        user_input = {
            "main_climate_entity": "climate.main",
            # outdoor_temperature_sensor not provided (removing it)
        }

        result = await options_flow.async_step_edit_main(user_input)

        # Should create entry successfully
        assert result["type"] == "create_entry"
        # Config should be updated
        mock_hass.config_entries.async_update_entry.assert_called_once()
        # Integration should be reloaded
        mock_hass.config_entries.async_reload.assert_called_once()
