"""Unit tests for device hierarchy."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from homeassistant.const import ATTR_TEMPERATURE
from custom_components.multizone_climate.climate import ZoneClimateEntity
from custom_components.multizone_climate.const import DOMAIN


class TestDeviceHierarchy:
    """Test the device hierarchy structure."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = MagicMock()
        coordinator.get_config = MagicMock(return_value={"satisfaction_eps": 0.0})
        coordinator.get_main_climate_data = MagicMock(
            return_value={
                "current_temperature": 20.0,
                "target_temperature": 21.0,
                "hvac_action": "heating",
            }
        )
        return coordinator

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        redis_client = MagicMock()
        redis_client.set_zone_state = AsyncMock()
        redis_client.enqueue_job = AsyncMock()
        return redis_client

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.data = {"main_climate_entity": "climate.main"}
        return entry

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=MagicMock(state="20.5"))
        hass.loop = MagicMock()
        hass.loop.time = MagicMock(return_value=1234567890.0)
        return hass

    def test_zone_entity_has_unique_device_identifier(
        self, mock_coordinator, mock_redis_client, mock_config_entry, mock_hass
    ):
        """Test that each zone entity has a unique device identifier."""
        zone_config = {
            "id": "bedroom_zone",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_temperature": 20.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
        }

        zone_entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="bedroom_zone",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        device_info = zone_entity.device_info

        # Check that device identifier is unique to this zone
        assert device_info["identifiers"] == {(DOMAIN, "zone_bedroom_zone")}
        assert device_info["name"] == "Multizone Climate - Bedroom"
        assert device_info["model"] == "Zone Controller"

    def test_zone_entity_has_via_device_link(
        self, mock_coordinator, mock_redis_client, mock_config_entry, mock_hass
    ):
        """Test that zone entity links to main device via via_device."""
        zone_config = {
            "id": "kitchen_zone",
            "name": "Kitchen",
            "temperature_sensor_entity_id": "sensor.kitchen_temp",
            "valve_switch_entity_id": "switch.kitchen_valve",
            "target_temperature": 21.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
        }

        zone_entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="kitchen_zone",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        device_info = zone_entity.device_info

        # Check that zone links to main device
        assert device_info["via_device"] == (DOMAIN, "main")

    def test_different_zones_have_different_identifiers(
        self, mock_coordinator, mock_redis_client, mock_config_entry, mock_hass
    ):
        """Test that different zones have different device identifiers."""
        zone1_config = {
            "id": "zone1",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
            "valve_switch_entity_id": "switch.bedroom_valve",
            "target_temperature": 20.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
        }

        zone2_config = {
            "id": "zone2",
            "name": "Kitchen",
            "temperature_sensor_entity_id": "sensor.kitchen_temp",
            "valve_switch_entity_id": "switch.kitchen_valve",
            "target_temperature": 21.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
        }

        zone1_entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone1",
            zone_config=zone1_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        zone2_entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="zone2",
            zone_config=zone2_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Check that identifiers are different
        assert zone1_entity.device_info["identifiers"] != zone2_entity.device_info[
            "identifiers"
        ]
        assert zone1_entity.device_info["identifiers"] == {(DOMAIN, "zone_zone1")}
        assert zone2_entity.device_info["identifiers"] == {(DOMAIN, "zone_zone2")}

    def test_zone_entity_unique_id_uses_zone_id(
        self, mock_coordinator, mock_redis_client, mock_config_entry, mock_hass
    ):
        """Test that zone entity unique_id includes zone_id."""
        zone_config = {
            "id": "test_zone_123",
            "name": "Test Zone",
            "temperature_sensor_entity_id": "sensor.test_temp",
            "valve_switch_entity_id": "switch.test_valve",
            "target_temperature": 20.0,
            "opening_offset": 0.3,
            "closing_offset": 0.3,
            "priority": 50,
            "is_fallback_valve": False,
        }

        zone_entity = ZoneClimateEntity(
            coordinator=mock_coordinator,
            redis_client=mock_redis_client,
            zone_id="test_zone_123",
            zone_config=zone_config,
            config_entry=mock_config_entry,
            hass=mock_hass,
        )

        # Check unique_id format
        assert zone_entity.unique_id == f"{DOMAIN}_zone_test_zone_123"
