"""Tests for multizone disabled behavior."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.multizone_climate.jobs.calculate_main_temp import (
    CalculateMainTempJob,
)
from custom_components.multizone_climate.core.valve_control import ValveController


class TestMultizoneDisabledBehavior:
    """Test behavior when multizone switch is OFF."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        redis_client = MagicMock()
        redis_client.get_config = AsyncMock()
        redis_client.get_zone_ids = AsyncMock()
        redis_client.get_zone_state = AsyncMock()
        redis_client.get_main_climate_state = AsyncMock()
        redis_client.set_valve_lock = AsyncMock()
        redis_client.is_valve_locked = AsyncMock(return_value=False)
        return redis_client

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass instance."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.loop = MagicMock()
        hass.loop.time = MagicMock(return_value=1234567890.0)
        return hass

    @pytest.mark.asyncio
    async def test_calculate_main_temp_skipped_when_multizone_disabled(
        self, mock_redis_client, mock_hass
    ):
        """Test that calculate_main_temp is skipped when multizone is disabled."""
        # Setup: multizone disabled
        mock_redis_client.get_config.return_value = {
            "multizone_enabled": False,
            "main_climate_entity_id": "climate.main",
        }

        job = CalculateMainTempJob(mock_redis_client, mock_hass)

        result = await job._execute_impl({})

        # Should skip calculation
        assert result["main_target_calculated"] is None
        assert result["main_target_updated"] is False
        assert result["zones_processed"] == 0
        assert result["skipped_reason"] == "multizone_disabled"

        # Should NOT call hass services
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_main_temp_runs_when_multizone_enabled(
        self, mock_redis_client, mock_hass
    ):
        """Test that calculate_main_temp runs normally when multizone is enabled."""
        # Setup: multizone enabled with zones
        mock_redis_client.get_config.return_value = {
            "multizone_enabled": True,
            "main_climate_entity_id": "climate.main",
            "use_average_mode": False,
            "main_target_all_zones_satisfied": 0.5,
            "main_min_temp": 18.0,
            "main_max_temp": 30.0,
            "main_change_threshold": 0.5,
        }
        mock_redis_client.get_zone_ids.return_value = ["zone1"]
        mock_redis_client.get_zone_state.return_value = {
            "id": "zone1",
            "state": "ON",
            "target_temperature": 22.0,
            "current_temperature": 21.0,
            "satisfaction": "underheated",
        }
        mock_redis_client.get_main_climate_state.return_value = {
            "target_temperature": 20.0,
            "current_temperature": 20.0,
        }

        job = CalculateMainTempJob(mock_redis_client, mock_hass)

        result = await job._execute_impl({})

        # Should calculate a new target
        assert result["main_target_calculated"] is not None
        assert result["zones_processed"] == 1
        assert "skipped_reason" not in result

    @pytest.mark.asyncio
    async def test_valves_controlled_individually_when_multizone_disabled(
        self, mock_redis_client
    ):
        """Test that zones control valves individually when multizone is disabled."""
        config = {
            "multizone_enabled": False,
            "min_valves_open": 1,
            "valve_actuation_delay": 120,
        }

        controller = ValveController(mock_redis_client, config)

        zones = [
            {
                "id": "zone1",
                "state": "ON",
                "valve_id": "switch.zone1_valve",
                "current_temperature": 19.0,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "valve_state": "closed",
            },
            {
                "id": "zone2",
                "state": "ON",
                "valve_id": "switch.zone2_valve",
                "current_temperature": 22.5,
                "target_temperature": 21.0,
                "satisfaction": "overheated",
                "valve_state": "open",
            },
            {
                "id": "zone3",
                "state": "ON",
                "valve_id": "switch.zone3_valve",
                "current_temperature": 21.0,
                "target_temperature": 21.0,
                "satisfaction": "satisfied",
                "valve_state": "closed",
            },
        ]

        actions = await controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=False,
        )

        # Should return individual zone valve actions
        # Underheated -> open
        # Overheated -> close
        # Satisfied -> open (to maintain)
        assert len(actions) == 3

        action_map = {action["valve_id"]: action["action"] for action in actions}
        assert action_map["switch.zone1_valve"] == "open"  # underheated
        assert action_map["switch.zone2_valve"] == "close"  # overheated
        assert action_map["switch.zone3_valve"] == "open"  # satisfied (maintain)

    @pytest.mark.asyncio
    async def test_valves_use_multizone_logic_when_enabled(
        self, mock_redis_client
    ):
        """Test that valves use multizone logic when multizone is enabled."""
        config = {
            "multizone_enabled": True,
            "min_valves_open": 1,
            "valve_actuation_delay": 120,
        }

        controller = ValveController(mock_redis_client, config)

        zones = [
            {
                "id": "zone1",
                "state": "ON",
                "valve_id": "switch.zone1_valve",
                "current_temperature": 19.0,
                "target_temperature": 21.0,
                "satisfaction": "underheated",
                "valve_state": "closed",
                "priority": 100,
                "is_fallback_valve": True,
            },
            {
                "id": "zone2",
                "state": "ON",
                "valve_id": "switch.zone2_valve",
                "current_temperature": 22.5,
                "target_temperature": 21.0,
                "satisfaction": "overheated",
                "valve_state": "open",
                "priority": 50,
                "is_fallback_valve": False,
            },
            {
                "id": "zone3",
                "state": "ON",
                "valve_id": "switch.zone3_valve",
                "current_temperature": 21.0,
                "target_temperature": 21.0,
                "satisfaction": "satisfied",
                "valve_state": "closed",
                "priority": 75,
                "is_fallback_valve": False,
            },
        ]

        actions = await controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            multizone_enabled=True,
        )

        # When multizone is enabled:
        # - Underheated zones: open valve
        # - Overheated zones: close valve
        # - Satisfied zones: leave in current state (hysteresis)
        # So we should see: zone1 open, zone2 close, zone3 unchanged

        action_map = {action["valve_id"]: action["action"] for action in actions}
        assert action_map.get("switch.zone1_valve") == "open"  # underheated
        assert action_map.get("switch.zone2_valve") == "close"  # overheated
        # zone3 (satisfied) should not be in actions (leave in current state)
        assert "switch.zone3_valve" not in action_map
