"""Unit tests for Redis initialization in __init__.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.multizone_climate import async_setup_entry


class TestRedisInitialization:
    """Test Redis initialization during setup."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.data = {}
        hass.loop = MagicMock()
        hass.loop.time = MagicMock(return_value=1234567890)

        # Mock states
        hass.states = MagicMock()
        main_climate_state = MagicMock()
        main_climate_state.state = "heat"
        main_climate_state.attributes = {
            "current_temperature": 21.5,
            "temperature": 22.0,
            "hvac_action": "heating",
        }

        outdoor_sensor_state = MagicMock()
        outdoor_sensor_state.state = "5.0"

        def mock_get_state(entity_id):
            if entity_id == "climate.main_thermostat":
                return main_climate_state
            elif entity_id == "sensor.outdoor_temp":
                return outdoor_sensor_state
            return None

        hass.states.get = mock_get_state

        # Mock config_entries
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {
            "main_climate_entity": "climate.main_thermostat",
            "outdoor_temperature_sensor": "sensor.outdoor_temp",
            "zone_name": "Fallback Zone",
            "temperature_sensor": "sensor.bedroom_temp",
            "valve_switch": "switch.bedroom_valve",
            "target_temperature": 20.0,
            "priority": 50,
        }
        entry.add_update_listener = MagicMock(return_value=lambda: None)
        entry.async_on_unload = MagicMock()
        return entry

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = MagicMock()
        client.connect = AsyncMock()
        client.get_config = AsyncMock(return_value={})  # Empty = needs initialization
        client.set_config = AsyncMock()
        client.get_main_climate_state = AsyncMock(return_value={})  # Empty = needs initialization
        client.set_main_climate_state = AsyncMock()
        client.get_zone_ids = AsyncMock(return_value=[])  # No zones yet
        client.add_zone = AsyncMock()
        return client

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_add_listener = MagicMock(return_value=lambda: None)
        return coordinator

    @pytest.fixture
    def mock_aiohttp_session(self):
        """Create mock aiohttp.ClientSession to prevent thread creation."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_response)
        return mock_session

    @pytest.mark.asyncio
    async def test_initializes_config_when_empty(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that global config is initialized when it doesn't exist."""
        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should call set_config once
        mock_redis_client.set_config.assert_called_once()

        # Verify config contents
        config_call_args = mock_redis_client.set_config.call_args[0][0]
        assert config_call_args["main_climate_entity_id"] == "climate.main_thermostat"
        assert config_call_args["outdoor_temperature_sensor"] == "sensor.outdoor_temp"
        assert config_call_args["min_valves_open"] == 1
        assert config_call_args["multizone_enabled"] is False
        assert config_call_args["coordinator_interval"] == 15  # Should be 15, not 8080

    @pytest.mark.asyncio
    async def test_initializes_main_climate_state_when_empty(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that main climate state is initialized when it doesn't exist."""
        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should call set_main_climate_state once
        mock_redis_client.set_main_climate_state.assert_called_once()

        # Verify main climate state contents
        state_call_args = mock_redis_client.set_main_climate_state.call_args[0][0]
        assert state_call_args["entity_id"] == "climate.main_thermostat"
        assert state_call_args["current_temperature"] == 21.5
        assert state_call_args["target_temperature"] == 22.0
        assert state_call_args["outdoor_temperature"] == 5.0
        assert state_call_args["hvac_mode"] == "heat"
        assert state_call_args["hvac_action"] == "heating"
        # multizone_enabled should NOT be in main_climate state (it's in config)
        assert "multizone_enabled" not in state_call_args

    @pytest.mark.asyncio
    async def test_skips_initialization_when_config_exists(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that config initialization is skipped when config already exists."""
        # Mock that config already exists
        mock_redis_client.get_config = AsyncMock(return_value={
            "main_climate_entity_id": "climate.existing",
            "min_valves_open": 2,
        })

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should NOT call set_config (already exists)
        mock_redis_client.set_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_initialization_when_main_climate_state_exists(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that main climate state initialization is skipped when it already exists."""
        # Mock that main climate state already exists
        mock_redis_client.get_main_climate_state = AsyncMock(return_value={
            "entity_id": "climate.existing",
            "current_temperature": 19.0,
        })

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should NOT call set_main_climate_state (already exists)
        mock_redis_client.set_main_climate_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_missing_outdoor_sensor_gracefully(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that missing outdoor temperature sensor is handled gracefully."""
        # Remove outdoor sensor from config
        mock_config_entry.data = {
            "main_climate_entity": "climate.main_thermostat",
            "zone_name": "Fallback Zone",
            "temperature_sensor": "sensor.bedroom_temp",
            "valve_switch": "switch.bedroom_valve",
        }

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should call set_main_climate_state
        mock_redis_client.set_main_climate_state.assert_called_once()

        # Verify outdoor temperature defaults to 0.0
        state_call_args = mock_redis_client.set_main_climate_state.call_args[0][0]
        assert state_call_args["outdoor_temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_invalid_outdoor_temperature(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that invalid outdoor temperature value is handled gracefully."""
        # Mock outdoor sensor with invalid state
        outdoor_sensor_state = MagicMock()
        outdoor_sensor_state.state = "unavailable"

        def mock_get_state(entity_id):
            if entity_id == "sensor.outdoor_temp":
                return outdoor_sensor_state
            return None

        mock_hass.states.get = mock_get_state

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should call set_main_climate_state
        mock_redis_client.set_main_climate_state.assert_called_once()

        # Verify outdoor temperature defaults to 0.0 when parsing fails
        state_call_args = mock_redis_client.set_main_climate_state.call_args[0][0]
        assert state_call_args["outdoor_temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_uses_defaults_when_entity_not_available_after_retry(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that main climate state uses defaults when entity is not available after retry."""
        # Mock that main climate entity is not available
        mock_hass.states.get = MagicMock(return_value=None)

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                                result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should sleep once for retry
        mock_sleep.assert_called_once_with(1)

        # Should call set_main_climate_state with defaults
        mock_redis_client.set_main_climate_state.assert_called_once()
        state_call_args = mock_redis_client.set_main_climate_state.call_args[0][0]
        assert state_call_args["entity_id"] == "climate.main_thermostat"
        assert state_call_args["current_temperature"] == 0.0
        assert state_call_args["target_temperature"] == 22.0  # Changed from 20.0 to 22.0
        assert state_call_args["outdoor_temperature"] == 0.0
        assert state_call_args["hvac_mode"] == "unknown"
        assert state_call_args["hvac_action"] == "idle"

    @pytest.mark.asyncio
    async def test_entity_available_on_retry(
        self, mock_hass, mock_config_entry, mock_redis_client, mock_coordinator, mock_aiohttp_session
    ):
        """Test that entity becomes available on retry attempt."""
        # Mock that entity is not available first time, but available on retry
        main_climate_state = MagicMock()
        main_climate_state.state = "heat"
        main_climate_state.attributes = {
            "current_temperature": 21.5,
            "temperature": 22.0,
            "hvac_action": "heating",
        }

        call_count = [0]
        def mock_get_state(entity_id):
            if entity_id == "climate.main_thermostat":
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call - entity not available
                    return None
                else:
                    # Second call (after retry) - entity available
                    return main_climate_state
            return None

        mock_hass.states.get = mock_get_state

        with patch("custom_components.multizone_climate.RedisClient", return_value=mock_redis_client):
            with patch("custom_components.multizone_climate.MultizoneClimateCoordinator", return_value=mock_coordinator):
                with patch("homeassistant.helpers.device_registry.async_get"):
                    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
                        with patch.dict("os.environ", {"BACKEND_PORT": "8080", "COORDINATOR_INTERVAL": "15"}):
                            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                                result = await async_setup_entry(mock_hass, mock_config_entry)

        # Should return True for successful setup
        assert result is True

        # Should sleep once for retry
        mock_sleep.assert_called_once_with(1)

        # Should call set_main_climate_state with actual data (not defaults)
        mock_redis_client.set_main_climate_state.assert_called_once()
        state_call_args = mock_redis_client.set_main_climate_state.call_args[0][0]
        assert state_call_args["entity_id"] == "climate.main_thermostat"
        assert state_call_args["current_temperature"] == 21.5
        assert state_call_args["target_temperature"] == 22.0
        assert state_call_args["hvac_mode"] == "heat"
        assert state_call_args["hvac_action"] == "heating"
