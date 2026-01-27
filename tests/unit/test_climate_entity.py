"""Unit tests for the climate.py ZoneClimateEntity."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_TEMPERATURE

from custom_components.multizone_climate.climate import (
    ZoneClimateEntity,
)


class TestZoneClimateEntity:
    """Test the ZoneClimateEntity class."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.backend_url = "http://localhost:8080"
        coordinator.session = MagicMock()
        coordinator.push_state_update = AsyncMock()
        coordinator.get_config = MagicMock(
            return_value={"main_climate_entity": "climate.main_thermostat"}
        )
        return coordinator

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        redis_client = MagicMock()
        redis_client.set_zone_state = AsyncMock()
        redis_client.enqueue_job = AsyncMock()
        redis_client.get_zone_state = AsyncMock(
            return_value={
                "id": "zone1",
                "name": "Bedroom",
                "temperature_sensor": "sensor.bedroom_temp",
                "valve_switch": "switch.bedroom_valve",
                "target_temperature": 21.0,
                "opening_offset": 0.3,
                "closing_offset": 0.3,
                "priority": 50,
                "is_fallback_valve": False,
                "current_temperature": 20.5,
                "satisfaction": "satisfied",
                "valve_state": "closed",
            }
        )
        return redis_client

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
        hass.loop = MagicMock()
        hass.loop.time = MagicMock(return_value=1234567890.0)
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_id"
        return config_entry

    @pytest.fixture
    def zone_config(self):
        """Create zone configuration."""
        return {
            "id": "zone1",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_temperature": 21.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
            "current_temperature": 20.5,
            "satisfaction": "satisfied",
            "valve_state": "closed",
        }

    def test_entity_initialization(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test entity initializes with correct properties."""
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        assert entity.name == "Bedroom"
        assert entity.zone_id == "zone1"
        assert entity._target_temperature == 21.0

    async def test_set_temperature(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test setting target temperature updates Redis and triggers jobs."""
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Mock async_write_ha_state to avoid threading issues in tests
        with patch.object(entity, "async_write_ha_state"):
            # Set new temperature
            await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

        # Verify temperature was updated locally
        assert entity._target_temperature == 22.0

        # Verify Redis was updated
        mock_redis_client.set_zone_state.assert_awaited()

    def test_extra_state_attributes(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test extra state attributes include zone configuration."""
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        attrs = entity.extra_state_attributes

        assert "satisfaction" in attrs
        assert attrs["satisfaction"] == "satisfied"
        assert "valve_state" in attrs
        assert "priority" in attrs
        assert "is_fallback_valve" in attrs

    @pytest.mark.asyncio
    async def test_turn_off_zone(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test turning off a zone (setting HVAC mode to OFF)."""
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Mock get_zone_ids to return just this zone
        mock_redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])

        # Initially enabled
        assert entity._enabled is True
        assert entity.hvac_mode == HVACMode.HEAT

        # Mock async_write_ha_state to avoid threading issues
        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_hvac_mode(HVACMode.OFF)

        # Verify zone is disabled
        assert entity._enabled is False
        assert entity.hvac_mode == HVACMode.OFF

        # Verify Redis was updated
        mock_redis_client.set_zone_state.assert_awaited()

        # Verify job was enqueued
        mock_redis_client.enqueue_job.assert_awaited()

    @pytest.mark.asyncio
    async def test_turn_on_zone(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test turning on a zone (setting HVAC mode to HEAT)."""
        # Start with disabled zone
        zone_config["enabled"] = "false"
        
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Initially disabled
        assert entity._enabled is False
        assert entity.hvac_mode == HVACMode.OFF

        # Mock async_write_ha_state to avoid threading issues
        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_hvac_mode(HVACMode.HEAT)

        # Verify zone is enabled
        assert entity._enabled is True
        assert entity.hvac_mode == HVACMode.HEAT

        # Verify Redis was updated
        mock_redis_client.set_zone_state.assert_awaited()

        # Verify job was enqueued
        mock_redis_client.enqueue_job.assert_awaited()

    @pytest.mark.asyncio
    async def test_cannot_disable_last_fallback_zone(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test that last fallback zone cannot be disabled."""
        # Make this a fallback zone
        zone_config["is_fallback_valve"] = True
        
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Mock get_zone_ids to return only this zone
        mock_redis_client.get_zone_ids = AsyncMock(return_value=["zone1"])
        
        # Mock coordinator to require at least 1 fallback zone
        mock_coordinator.get_config = MagicMock(
            return_value={"min_valves_open": 1}
        )

        # Try to disable - should raise ValueError
        with pytest.raises(ValueError, match="Cannot disable this fallback zone"):
            with patch.object(entity, "async_write_ha_state"):
                await entity.async_set_hvac_mode(HVACMode.OFF)

        # Verify zone is still enabled
        assert entity._enabled is True

    @pytest.mark.asyncio
    async def test_can_disable_fallback_zone_when_others_exist(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test that fallback zone can be disabled when other fallback zones exist."""
        # Make this a fallback zone
        zone_config["is_fallback_valve"] = True
        
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Mock get_zone_ids to return two zones
        mock_redis_client.get_zone_ids = AsyncMock(return_value=["zone1", "zone2"])
        
        # Mock get_zone_state for zone2 (another enabled fallback zone)
        async def mock_get_zone_state(zone_id):
            if zone_id == "zone2":
                return {
                    "id": "zone2",
                    "is_fallback_valve": True,
                    "enabled": "true",
                }
            return None
        
        mock_redis_client.get_zone_state = AsyncMock(side_effect=mock_get_zone_state)
        
        # Mock coordinator to require at least 1 fallback zone
        mock_coordinator.get_config = MagicMock(
            return_value={"min_valves_open": 1}
        )

        # Should be able to disable
        with patch.object(entity, "async_write_ha_state"):
            await entity.async_set_hvac_mode(HVACMode.OFF)

        # Verify zone is disabled
        assert entity._enabled is False

        # Verify Redis was updated
        mock_redis_client.set_zone_state.assert_awaited()

        # Verify job was enqueued
        mock_redis_client.enqueue_job.assert_awaited()

    def test_hvac_modes_includes_off(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test that HVAC modes includes both HEAT and OFF."""
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        assert HVACMode.HEAT in entity.hvac_modes
        assert HVACMode.OFF in entity.hvac_modes

    def test_supported_features_includes_turn_on_off(
        self,
        mock_coordinator,
        mock_redis_client,
        mock_hass,
        mock_config_entry,
        zone_config,
    ):
        """Test that supported features includes TURN_ON and TURN_OFF."""
        from homeassistant.components.climate import ClimateEntityFeature
        
        entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        features = entity.supported_features
        assert features & ClimateEntityFeature.TURN_ON
        assert features & ClimateEntityFeature.TURN_OFF
        assert features & ClimateEntityFeature.TARGET_TEMPERATURE

