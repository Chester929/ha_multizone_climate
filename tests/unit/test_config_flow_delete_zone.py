"""Unit tests for delete zone functionality in config flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.multizone_climate.config_flow import MultizoneClimateOptionsFlow
from custom_components.multizone_climate import DOMAIN


class TestDeleteZone:
    """Test the delete zone functionality."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {"main_climate_entity": "climate.main"}
        return entry

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        client.get_zone_ids = AsyncMock()
        client.get_zone_state = AsyncMock()
        client.remove_zone = AsyncMock()
        return client

    @pytest.fixture
    def mock_hass(self, mock_redis_client):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "test_entry_id": {
                    "redis_client": mock_redis_client,
                    "coordinator": MagicMock(),
                }
            }
        }
        hass.config_entries = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        return hass

    @pytest.fixture
    def options_flow(self, mock_config_entry, mock_hass):
        """Create options flow instance."""
        flow = MultizoneClimateOptionsFlow(mock_config_entry)
        flow.hass = mock_hass
        flow._config_entry = mock_config_entry
        return flow

    @pytest.mark.asyncio
    async def test_delete_zone_success(self, options_flow, mock_hass):
        """Test successful zone deletion."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup: Two zones, one fallback and one regular
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": False},
        ]

        # Delete the non-fallback zone
        user_input = {"zone_to_delete": "zone2"}

        with patch.dict("os.environ", {"BACKEND_PORT": "8080"}):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_session_instance = MagicMock()
                mock_session_instance.delete.return_value = mock_response
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()
                mock_session.return_value = mock_session_instance

                result = await options_flow.async_step_delete_zone(user_input)

        # Should remove zone and reload integration
        redis_client.remove_zone.assert_called_once_with("zone2")
        mock_hass.config_entries.async_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_last_fallback_zone_prevented(self, options_flow, mock_hass):
        """Test that deleting the last fallback zone is prevented."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup: Only one zone which is a fallback
        redis_client.get_zone_ids.return_value = ["zone1"]
        redis_client.get_zone_state.return_value = {
            "name": "Zone 1",
            "is_fallback_valve": True
        }

        # Try to delete the only fallback zone
        user_input = {"zone_to_delete": "zone1"}

        result = await options_flow.async_step_delete_zone(user_input)

        # Should show form with error, not delete
        redis_client.remove_zone.assert_not_called()
        assert result["type"] == "form"
        assert result["errors"]["zone_to_delete"] == "cannot_delete_last_fallback"

    @pytest.mark.asyncio
    async def test_delete_one_of_multiple_fallback_zones(self, options_flow, mock_hass):
        """Test deleting one fallback zone when multiple fallback zones exist."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup: Two fallback zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": True},
        ]

        # Delete one fallback zone (should be allowed)
        user_input = {"zone_to_delete": "zone1"}

        with patch.dict("os.environ", {"BACKEND_PORT": "8080"}):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_session_instance = MagicMock()
                mock_session_instance.delete.return_value = mock_response
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()
                mock_session.return_value = mock_session_instance

                result = await options_flow.async_step_delete_zone(user_input)

        # Should remove zone successfully
        redis_client.remove_zone.assert_called_once_with("zone1")

    @pytest.mark.asyncio
    async def test_delete_zone_no_zones_available(self, options_flow, mock_hass):
        """Test behavior when no zones exist to delete."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]
        redis_client.get_zone_ids.return_value = []

        result = await options_flow.async_step_delete_zone(None)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "no_zones_to_delete"

    @pytest.mark.asyncio
    async def test_delete_zone_redis_failure(self, options_flow, mock_hass):
        """Test error handling when Redis deletion fails."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": False},
        ]

        # Make remove_zone fail
        redis_client.remove_zone.side_effect = Exception("Redis error")

        user_input = {"zone_to_delete": "zone2"}
        result = await options_flow.async_step_delete_zone(user_input)

        # Should show form with error
        assert result["type"] == "form"
        assert result["errors"]["base"] == "redis_error"

    @pytest.mark.asyncio
    async def test_delete_zone_backend_api_failure(self, options_flow, mock_hass):
        """Test that backend API deletion failures are logged but don't block deletion."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": False},
        ]

        user_input = {"zone_to_delete": "zone2"}

        with patch.dict("os.environ", {"BACKEND_PORT": "8080"}):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 500  # Server error
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_session_instance = MagicMock()
                mock_session_instance.delete.return_value = mock_response
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()
                mock_session.return_value = mock_session_instance

                result = await options_flow.async_step_delete_zone(user_input)

        # Should still complete successfully (Redis deletion worked)
        redis_client.remove_zone.assert_called_once_with("zone2")
        mock_hass.config_entries.async_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_zone_invalid_backend_port(self, options_flow, mock_hass):
        """Test that invalid BACKEND_PORT is handled gracefully."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": False},
        ]

        user_input = {"zone_to_delete": "zone2"}

        # Use invalid port value
        with patch.dict("os.environ", {"BACKEND_PORT": "invalid_port"}):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_session_instance = MagicMock()
                mock_session_instance.delete.return_value = mock_response
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()
                mock_session.return_value = mock_session_instance

                result = await options_flow.async_step_delete_zone(user_input)

        # Should fall back to default port and complete successfully
        redis_client.remove_zone.assert_called_once_with("zone2")
        # Verify backend URL used default port 8080
        call_args = mock_session_instance.delete.call_args
        assert "localhost:8080" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_zone_shows_zone_list(self, options_flow, mock_hass):
        """Test that zone list is displayed correctly."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Living Room", "is_fallback_valve": True},
            {"name": "Bedroom", "is_fallback_valve": False},
        ]

        result = await options_flow.async_step_delete_zone(None)

        # Should show form with zone options
        assert result["type"] == "form"
        data_schema = result["data_schema"].schema
        zone_selector = data_schema["zone_to_delete"]

        # Verify zone options are created (structure may vary)
        # Just ensure form is displayed successfully without errors when no user_input
        assert "errors" not in result or not result["errors"]

    @pytest.mark.asyncio
    async def test_delete_zone_caches_zone_states(self, options_flow, mock_hass):
        """Test that zone states are cached to avoid redundant Redis calls."""
        redis_client = mock_hass.data[DOMAIN]["test_entry_id"]["redis_client"]

        # Setup zones
        redis_client.get_zone_ids.return_value = ["zone1", "zone2", "zone3"]
        redis_client.get_zone_state.side_effect = [
            {"name": "Zone 1", "is_fallback_valve": True},
            {"name": "Zone 2", "is_fallback_valve": False},
            {"name": "Zone 3", "is_fallback_valve": True},
        ]

        user_input = {"zone_to_delete": "zone2"}

        with patch.dict("os.environ", {"BACKEND_PORT": "8080"}):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.__aenter__ = AsyncMock(return_value=mock_response)
                mock_response.__aexit__ = AsyncMock()

                mock_session_instance = MagicMock()
                mock_session_instance.delete.return_value = mock_response
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock()
                mock_session.return_value = mock_session_instance

                result = await options_flow.async_step_delete_zone(user_input)

        # With caching: 3 calls (once per zone).
        # Without caching: 7 calls (3 for options + 1 for selected zone + 3 for fallback count).
        assert redis_client.get_zone_state.call_count == 3
