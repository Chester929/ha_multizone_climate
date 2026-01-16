"""Integration tests for config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.multizone_climate.config_flow import (
    MultizoneClimateConfigFlow,
    MultizoneClimateOptionsFlow,
)
from custom_components.multizone_climate.const import (
    DOMAIN,
    CONF_REDIS_HOST,
    CONF_REDIS_PORT,
    CONF_REDIS_PASSWORD,
    CONF_REDIS_DB,
    CONF_REDIS_KEY_PREFIX,
    CONF_MAIN_CLIMATE_ENTITY,
    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
    CONF_USE_AVERAGE_MODE,
    CONF_MIN_VALVES_OPEN,
    CONF_MAIN_MIN_TEMP,
    CONF_MAIN_MAX_TEMP,
    CONF_MAIN_CHANGE_THRESHOLD,
    CONF_VALVE_ACTUATION_DELAY,
    CONF_COORDINATOR_INTERVAL,
    CONF_SATISFACTION_EPS,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_KEY_PREFIX,
)


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    with patch(
        "custom_components.multizone_climate.config_flow.RedisClient"
    ) as mock_client:
        instance = AsyncMock()
        instance.connect = AsyncMock()
        instance.disconnect = AsyncMock()
        instance.set_config = AsyncMock()
        mock_client.return_value = instance
        yield mock_client


@pytest.fixture
def mock_entity_registry(hass):
    """Create mock entity registry."""
    registry = MagicMock()
    entity_entry = MagicMock()
    entity_entry.entity_id = "climate.test_climate"
    registry.async_get.return_value = entity_entry
    
    with patch(
        "custom_components.multizone_climate.config_flow.er.async_get",
        return_value=registry,
    ):
        yield registry


class TestConfigFlow:
    """Test the config flow."""

    async def test_user_step_success(self, hass: HomeAssistant, mock_redis_client):
        """Test successful user step with Redis connection."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        # Test initial form display
        result = await flow.async_step_user()
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None

        # Test form submission with valid data
        user_input = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "multizone",
        }

        result = await flow.async_step_user(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "main_climate"
        assert mock_redis_client.called

    async def test_user_step_cannot_connect(
        self, hass: HomeAssistant, mock_redis_client
    ):
        """Test user step when Redis connection fails."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        # Mock connection error
        mock_redis_client.return_value.connect.side_effect = ConnectionError(
            "Cannot connect"
        )

        user_input = {
            CONF_REDIS_HOST: "invalid_host",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "",
        }

        result = await flow.async_step_user(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_user_step_unknown_error(
        self, hass: HomeAssistant, mock_redis_client
    ):
        """Test user step with unknown error."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        # Mock unknown error
        mock_redis_client.return_value.connect.side_effect = Exception("Unknown error")

        user_input = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "",
        }

        result = await flow.async_step_user(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"

    async def test_main_climate_step_success(
        self, hass: HomeAssistant, mock_redis_client, mock_entity_registry
    ):
        """Test successful main climate step."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass
        flow._data = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "",
        }

        # Test initial form display
        result = await flow.async_step_main_climate()
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "main_climate"

        # Test form submission with valid entity
        user_input = {CONF_MAIN_CLIMATE_ENTITY: "climate.test_climate"}

        result = await flow.async_step_main_climate(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "automation_config"

    async def test_main_climate_step_invalid_entity(
        self, hass: HomeAssistant, mock_redis_client
    ):
        """Test main climate step with invalid entity."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        # Mock entity registry returning None
        with patch(
            "custom_components.multizone_climate.config_flow.er.async_get"
        ) as mock_get:
            registry = MagicMock()
            registry.async_get.return_value = None
            mock_get.return_value = registry

            user_input = {CONF_MAIN_CLIMATE_ENTITY: "climate.nonexistent"}

            result = await flow.async_step_main_climate(user_input)
            assert result["type"] == data_entry_flow.FlowResultType.FORM
            assert result["step_id"] == "main_climate"
            assert result["errors"]["base"] == "invalid_entity"

    async def test_main_climate_step_not_climate_entity(
        self, hass: HomeAssistant, mock_redis_client, mock_entity_registry
    ):
        """Test main climate step with non-climate entity."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        user_input = {CONF_MAIN_CLIMATE_ENTITY: "sensor.temperature"}

        result = await flow.async_step_main_climate(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "main_climate"
        assert result["errors"]["base"] == "not_climate_entity"

    async def test_automation_config_step_success(
        self, hass: HomeAssistant, mock_redis_client, mock_entity_registry
    ):
        """Test successful automation config step."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass
        flow._data = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "",
            CONF_MAIN_CLIMATE_ENTITY: "climate.test_climate",
        }

        # Test initial form display
        result = await flow.async_step_automation_config()
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "automation_config"

        # Test form submission with valid data
        user_input = {
            CONF_USE_AVERAGE_MODE: False,
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
            CONF_MIN_VALVES_OPEN: 1,
            CONF_MAIN_MIN_TEMP: 18.0,
            CONF_MAIN_MAX_TEMP: 30.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        result = await flow.async_step_automation_config(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Multizone Climate (climate.test_climate)"
        assert CONF_USE_AVERAGE_MODE in result["data"]
        assert result["data"][CONF_MIN_VALVES_OPEN] == 1

    async def test_automation_config_invalid_temp_range(self, hass: HomeAssistant):
        """Test automation config with invalid temperature range."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        user_input = {
            CONF_USE_AVERAGE_MODE: True,
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
            CONF_MIN_VALVES_OPEN: 1,
            CONF_MAIN_MIN_TEMP: 30.0,  # Min > Max
            CONF_MAIN_MAX_TEMP: 18.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        result = await flow.async_step_automation_config(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_temp_range"

    async def test_automation_config_invalid_min_valves(self, hass: HomeAssistant):
        """Test automation config with invalid minimum valves."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        user_input = {
            CONF_USE_AVERAGE_MODE: True,
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
            CONF_MIN_VALVES_OPEN: 0,  # Invalid: must be >= 1
            CONF_MAIN_MIN_TEMP: 18.0,
            CONF_MAIN_MAX_TEMP: 30.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        result = await flow.async_step_automation_config(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_min_valves"

    async def test_automation_config_invalid_slider_value(self, hass: HomeAssistant):
        """Test automation config with invalid slider value."""
        flow = MultizoneClimateConfigFlow()
        flow.hass = hass

        user_input = {
            CONF_USE_AVERAGE_MODE: False,  # Slider mode
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 1.5,  # Invalid: must be 0-1
            CONF_MIN_VALVES_OPEN: 1,
            CONF_MAIN_MIN_TEMP: 18.0,
            CONF_MAIN_MAX_TEMP: 30.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        result = await flow.async_step_automation_config(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_slider_value"

    async def test_full_flow_success(
        self, hass: HomeAssistant, mock_redis_client, mock_entity_registry
    ):
        """Test complete config flow from start to finish."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        # Step 1: Redis configuration
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_REDIS_HOST: "localhost",
                CONF_REDIS_PORT: 6379,
                CONF_REDIS_DB: 0,
                CONF_REDIS_KEY_PREFIX: "test",
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "main_climate"

        # Step 2: Main climate entity
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAIN_CLIMATE_ENTITY: "climate.test_climate"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "automation_config"

        # Step 3: Automation configuration
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USE_AVERAGE_MODE: True,
                CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
                CONF_MIN_VALVES_OPEN: 1,
                CONF_MAIN_MIN_TEMP: 18.0,
                CONF_MAIN_MAX_TEMP: 30.0,
                CONF_MAIN_CHANGE_THRESHOLD: 0.5,
                CONF_VALVE_ACTUATION_DELAY: 60,
                CONF_COORDINATOR_INTERVAL: 15,
                CONF_SATISFACTION_EPS: 0.1,
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Multizone Climate (climate.test_climate)"


class TestOptionsFlow:
    """Test the options flow."""

    async def test_options_flow_init(self, hass: HomeAssistant):
        """Test options flow initialization."""
        entry = MagicMock()
        entry.data = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_MAIN_CLIMATE_ENTITY: "climate.test",
        }

        flow = MultizoneClimateOptionsFlow(entry)
        flow.hass = hass

        result = await flow.async_step_init()
        assert result["type"] == data_entry_flow.FlowResultType.MENU
        assert "config" in result["menu_options"]
        assert "zones" in result["menu_options"]

    async def test_options_flow_config_update_success(self, hass: HomeAssistant):
        """Test successful config update in options flow."""
        entry = MagicMock()
        entry.data = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_REDIS_DB: 0,
            CONF_REDIS_KEY_PREFIX: "",
            CONF_MAIN_CLIMATE_ENTITY: "climate.test",
            CONF_USE_AVERAGE_MODE: False,
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
            CONF_MIN_VALVES_OPEN: 1,
            CONF_MAIN_MIN_TEMP: 18.0,
            CONF_MAIN_MAX_TEMP: 30.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        flow = MultizoneClimateOptionsFlow(entry)
        flow.hass = hass

        # Mock config entries and Redis client
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()

        with patch(
            "custom_components.multizone_climate.config_flow.RedisClient"
        ) as mock_client:
            instance = AsyncMock()
            instance.connect = AsyncMock()
            instance.disconnect = AsyncMock()
            instance.set_config = AsyncMock()
            mock_client.return_value = instance

            user_input = {
                CONF_USE_AVERAGE_MODE: True,
                CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.6,
                CONF_MIN_VALVES_OPEN: 2,
                CONF_MAIN_MIN_TEMP: 19.0,
                CONF_MAIN_MAX_TEMP: 28.0,
                CONF_MAIN_CHANGE_THRESHOLD: 0.3,
                CONF_VALVE_ACTUATION_DELAY: 90,
                CONF_COORDINATOR_INTERVAL: 20,
                CONF_SATISFACTION_EPS: 0.2,
            }

            result = await flow.async_step_config(user_input)
            assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
            assert hass.config_entries.async_update_entry.called

    async def test_options_flow_config_invalid_temp_range(self, hass: HomeAssistant):
        """Test config update with invalid temperature range."""
        entry = MagicMock()
        entry.data = {
            CONF_REDIS_HOST: "localhost",
            CONF_REDIS_PORT: 6379,
            CONF_MAIN_CLIMATE_ENTITY: "climate.test",
        }

        flow = MultizoneClimateOptionsFlow(entry)
        flow.hass = hass

        user_input = {
            CONF_USE_AVERAGE_MODE: True,
            CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: 0.5,
            CONF_MIN_VALVES_OPEN: 1,
            CONF_MAIN_MIN_TEMP: 30.0,  # Min > Max
            CONF_MAIN_MAX_TEMP: 18.0,
            CONF_MAIN_CHANGE_THRESHOLD: 0.5,
            CONF_VALVE_ACTUATION_DELAY: 60,
            CONF_COORDINATOR_INTERVAL: 15,
            CONF_SATISFACTION_EPS: 0.1,
        }

        result = await flow.async_step_config(user_input)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_temp_range"
