"""Unit tests for unload and remove entry functionality in __init__.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.multizone_climate import async_unload_entry, async_remove_entry


class TestUnloadAndRemove:
    """Test unload and remove entry functions."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        client.disconnect = AsyncMock()
        client.clear_all_data = AsyncMock()
        client.connect = AsyncMock()
        return client

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.stop_job_worker = AsyncMock()
        coordinator.async_shutdown = AsyncMock()
        return coordinator

    @pytest.fixture
    def mock_valve_state_automation(self):
        """Create mock valve state automation."""
        automation = MagicMock()
        automation.stop = AsyncMock()
        return automation

    @pytest.mark.asyncio
    async def test_unload_preserves_redis_data_for_reload(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_valve_state_automation
    ):
        """Test that async_unload_entry does not clear Redis data (preserves data for reload)."""
        from custom_components.multizone_climate import DOMAIN

        # Setup hass.data
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "redis_client": mock_redis_client,
                    "coordinator": mock_coordinator,
                    "valve_state_automation": mock_valve_state_automation,
                }
            }
        }

        # Mock unload platforms on hass
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_config_entry)

        # Should return True
        assert result is True

        # Should stop automation
        mock_valve_state_automation.stop.assert_called_once()

        # Should stop coordinator
        mock_coordinator.stop_job_worker.assert_called_once()
        mock_coordinator.async_shutdown.assert_called_once()

        # Should disconnect from Redis
        mock_redis_client.disconnect.assert_called_once()

        # Should NOT clear Redis data (this is the key assertion)
        mock_redis_client.clear_all_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_handles_missing_automation(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator
    ):
        """Test that async_unload_entry handles missing valve_state_automation gracefully."""
        from custom_components.multizone_climate import DOMAIN

        # Setup hass.data without valve_state_automation
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "redis_client": mock_redis_client,
                    "coordinator": mock_coordinator,
                }
            }
        }

        # Mock unload platforms on hass
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass, mock_config_entry)

        # Should return True
        assert result is True

        # Should still complete successfully
        mock_coordinator.stop_job_worker.assert_called_once()
        mock_redis_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_clears_redis_data(self, mock_hass, mock_config_entry, mock_redis_client):
        """Test that async_remove_entry clears all Redis data."""
        # Mock RedisClient constructor
        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch.dict("os.environ", {"REDIS_HOST": "localhost", "REDIS_PORT": "6379"}):
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should connect to Redis
        mock_redis_client.connect.assert_called_once()

        # Should clear all Redis data
        mock_redis_client.clear_all_data.assert_called_once()

        # Should disconnect
        mock_redis_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_uses_environment_variables(self, mock_hass, mock_config_entry, mock_redis_client):
        """Test that async_remove_entry uses correct Redis configuration from environment."""
        with patch("custom_components.multizone_climate.RedisClient") as mock_redis_class:
            mock_redis_class.return_value = mock_redis_client
            with patch.dict("os.environ", {
                "REDIS_HOST": "test-redis-host",
                "REDIS_PORT": "9999",
                "REDIS_PASSWORD": "test-password"
            }):
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should create RedisClient with correct parameters
        mock_redis_class.assert_called_once_with(
            host="test-redis-host",
            port=9999,
            password="test-password",
        )

    @pytest.mark.asyncio
    async def test_remove_handles_default_environment_values(self, mock_hass, mock_config_entry, mock_redis_client):
        """Test that async_remove_entry uses default values when environment variables are not set."""
        with patch("custom_components.multizone_climate.RedisClient") as mock_redis_class:
            mock_redis_class.return_value = mock_redis_client
            # Clear environment variables
            with patch.dict("os.environ", {}, clear=True):
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should create RedisClient with default parameters
        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
        )

    @pytest.mark.asyncio
    async def test_remove_handles_redis_connection_failure(self, mock_hass, mock_config_entry):
        """Test that async_remove_entry handles Redis connection failures gracefully."""
        mock_redis_client = MagicMock()
        mock_redis_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
        mock_redis_client.disconnect = AsyncMock()

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch.dict("os.environ", {"REDIS_HOST": "localhost", "REDIS_PORT": "6379"}):
                # Should not raise exception - best-effort cleanup
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should attempt to connect
        mock_redis_client.connect.assert_called_once()
        # Should attempt to disconnect in finally block
        mock_redis_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_handles_clear_data_failure(self, mock_hass, mock_config_entry):
        """Test that async_remove_entry handles clear_all_data failures gracefully."""
        mock_redis_client = MagicMock()
        mock_redis_client.connect = AsyncMock()
        mock_redis_client.clear_all_data = AsyncMock(side_effect=Exception("Clear failed"))
        mock_redis_client.disconnect = AsyncMock()

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch.dict("os.environ", {"REDIS_HOST": "localhost", "REDIS_PORT": "6379"}):
                # Should not raise exception - best-effort cleanup
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should connect and attempt to clear
        mock_redis_client.connect.assert_called_once()
        mock_redis_client.clear_all_data.assert_called_once()
        # Should disconnect even after failure
        mock_redis_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_handles_disconnect_failure(self, mock_hass, mock_config_entry):
        """Test that async_remove_entry handles disconnect failures gracefully."""
        mock_redis_client = MagicMock()
        mock_redis_client.connect = AsyncMock()
        mock_redis_client.clear_all_data = AsyncMock()
        mock_redis_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch.dict("os.environ", {"REDIS_HOST": "localhost", "REDIS_PORT": "6379"}):
                # Should not raise exception - best-effort cleanup
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should complete the cleanup attempt
        mock_redis_client.connect.assert_called_once()
        mock_redis_client.clear_all_data.assert_called_once()
        mock_redis_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_handles_invalid_redis_port(self, mock_hass, mock_config_entry, mock_redis_client):
        """Test that async_remove_entry handles invalid REDIS_PORT values."""
        with patch("custom_components.multizone_climate.RedisClient") as mock_redis_class:
            mock_redis_class.return_value = mock_redis_client
            with patch.dict("os.environ", {"REDIS_PORT": "invalid_port"}):
                await async_remove_entry(mock_hass, mock_config_entry)

        # Should fall back to default port 6379
        mock_redis_class.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
        )
