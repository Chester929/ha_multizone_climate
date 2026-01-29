"""Unit tests for config flow validation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.multizone_climate.config_flow import (
    MultizoneClimateOptionsFlow,
)


class TestConfigFlowValidation:
    """Test the config flow validation logic."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {"main_climate_entity": "climate.main"}
        return entry

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=MagicMock())
        hass.data = {
            "multizone_climate": {
                "test_entry_id": {
                    "redis_client": MagicMock(),
                    "coordinator": MagicMock(),
                }
            }
        }
        return hass

    @pytest.fixture
    def options_flow(self, mock_config_entry, mock_hass):
        """Create options flow instance."""
        flow = MultizoneClimateOptionsFlow(mock_config_entry)
        flow.hass = mock_hass
        return flow

    @pytest.mark.asyncio
    async def test_duplicate_temperature_sensor_rejected(
        self, options_flow, mock_hass
    ):
        """Test that duplicate temperature sensors are rejected."""
        # Setup: existing zone with sensor
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])
        redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "name": "Bedroom",
                "temperature_sensor_entity_id": "sensor.bedroom_temp",
                "valve_switch_entity_id": "switch.bedroom_valve",
            }
        )
        redis_client.add_zone = AsyncMock()

        # Try to add new zone with same temperature sensor
        user_input = {
            "zone_name": "Living Room",
            "temperature_sensor": "sensor.bedroom_temp",  # Duplicate!
            "valve_switch": "switch.living_valve",
            "target_temperature": 21.0,
        }

        result = await options_flow.async_step_add_zone(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["temperature_sensor"] == "sensor_already_used"
        # Should NOT call add_zone
        redis_client.add_zone.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_valve_switch_rejected(self, options_flow, mock_hass):
        """Test that duplicate valve switches are rejected."""
        # Setup: existing zone with valve
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])
        redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "name": "Bedroom",
                "temperature_sensor_entity_id": "sensor.bedroom_temp",
                "valve_switch_entity_id": "switch.bedroom_valve",
            }
        )
        redis_client.add_zone = AsyncMock()

        # Try to add new zone with same valve switch
        user_input = {
            "zone_name": "Living Room",
            "temperature_sensor": "sensor.living_temp",
            "valve_switch": "switch.bedroom_valve",  # Duplicate!
            "target_temperature": 21.0,
        }

        result = await options_flow.async_step_add_zone(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["valve_switch"] == "valve_already_used"
        # Should NOT call add_zone
        redis_client.add_zone.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_zone_name_rejected(self, options_flow, mock_hass):
        """Test that duplicate zone names are rejected."""
        # Setup: existing zone with name
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])
        redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "name": "Bedroom",
                "temperature_sensor_entity_id": "sensor.bedroom_temp",
                "valve_switch_entity_id": "switch.bedroom_valve",
            }
        )
        redis_client.add_zone = AsyncMock()

        # Try to add new zone with same name
        user_input = {
            "zone_name": "Bedroom",  # Duplicate!
            "temperature_sensor": "sensor.living_temp",
            "valve_switch": "switch.living_valve",
            "target_temperature": 21.0,
        }

        result = await options_flow.async_step_add_zone(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["zone_name"] == "zone_name_already_used"
        # Should NOT call add_zone
        redis_client.add_zone.assert_not_called()

    @pytest.mark.asyncio
    async def test_unique_sensors_and_valves_accepted(self, options_flow, mock_hass):
        """Test that unique sensors and valves are accepted."""
        # Setup: existing zone
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])
        redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "name": "Bedroom",
                "temperature_sensor_entity_id": "sensor.bedroom_temp",
                "valve_switch_entity_id": "switch.bedroom_valve",
            }
        )
        redis_client.add_zone = AsyncMock()

        # Mock config_entries for reload
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_reload = AsyncMock()

        # Add zone with unique sensors and valves
        user_input = {
            "zone_name": "Living Room",
            "temperature_sensor": "sensor.living_temp",  # Unique
            "valve_switch": "switch.living_valve",  # Unique
            "target_temperature": 21.0,
        }

        with patch("uuid.uuid4", return_value="zone2"):
            with patch("os.environ.get", return_value="8080"):
                with patch("aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 201
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                        mock_response
                    )

                    result = await options_flow.async_step_add_zone(user_input)

        # Should succeed and call add_zone
        assert result["type"] == "create_entry"
        redis_client.add_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_zone_id_collision_rejected(self, options_flow, mock_hass):
        """Test that zone_id collisions are rejected."""
        # Setup: existing zone with specific ID
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(
            return_value=["zone1", "collision_id"]
        )
        redis_client.get_zone_state = AsyncMock(return_value=None)
        redis_client.add_zone = AsyncMock()

        user_input = {
            "zone_name": "Living Room",
            "temperature_sensor": "sensor.living_temp",
            "valve_switch": "switch.living_valve",
            "target_temperature": 21.0,
        }

        # Mock UUID to return a colliding ID
        with patch("uuid.uuid4", return_value="collision_id"):
            result = await options_flow.async_step_add_zone(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["base"] == "zone_id_collision"
        # Should NOT call add_zone
        redis_client.add_zone.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_existing_zones_allows_any_sensor(self, options_flow, mock_hass):
        """Test that any sensor is allowed when no zones exist."""
        # Setup: no existing zones
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=[])
        redis_client.add_zone = AsyncMock()

        # Mock config_entries for reload
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_reload = AsyncMock()

        user_input = {
            "zone_name": "First Zone",
            "temperature_sensor": "sensor.any_temp",
            "valve_switch": "switch.any_valve",
            "target_temperature": 21.0,
        }

        with patch("uuid.uuid4", return_value="zone1"):
            with patch("os.environ.get", return_value="8080"):
                with patch("aiohttp.ClientSession") as mock_session:
                    mock_response = MagicMock()
                    mock_response.status = 201
                    mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                        mock_response
                    )

                    result = await options_flow.async_step_add_zone(user_input)

        # Should succeed
        assert result["type"] == "create_entry"
        redis_client.add_zone.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_value_error_shows_collision_error(
        self, options_flow, mock_hass
    ):
        """Test that ValueError from redis_client shows zone_id_collision error."""
        # Setup
        redis_client = mock_hass.data["multizone_climate"]["test_entry_id"][
            "redis_client"
        ]
        redis_client.get_zone_ids = AsyncMock(return_value=[])
        # Simulate ValueError from add_zone (zone already exists)
        redis_client.add_zone = AsyncMock(
            side_effect=ValueError("Zone zone1 already exists")
        )

        user_input = {
            "zone_name": "Test Zone",
            "temperature_sensor": "sensor.test_temp",
            "valve_switch": "switch.test_valve",
            "target_temperature": 21.0,
        }

        with patch("uuid.uuid4", return_value="zone1"):
            result = await options_flow.async_step_add_zone(user_input)

        # Should show form with collision error
        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["base"] == "zone_id_collision"
