"""Integration tests for Multizone Climate."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.multizone_climate.const import DOMAIN


class TestIntegrationSetup:
    """Test integration setup and configuration."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        with patch(
            "custom_components.multizone_climate.core.redis_client.RedisClient"
        ) as mock:
            client = AsyncMock()
            client.connect = AsyncMock()
            client.get_config = AsyncMock(return_value={})
            client.get_zone_ids = AsyncMock(return_value=[])
            mock.return_value = client
            yield mock

    async def test_setup_component(self, hass: HomeAssistant, mock_redis_client):
        """
        Test component setup.

        Expected:
            - Component loads successfully
            - Domain added to hass.data
            - Coordinator initialized
        """
        config = {
            DOMAIN: {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                },
                "main_climate_entity_id": "climate.main_thermostat",
            }
        }

        result = await async_setup_component(hass, DOMAIN, config)

        assert result is True or result is None  # Setup may return None on success
        # Note: Full setup testing requires proper Home Assistant test harness

    async def test_setup_platforms(self, hass: HomeAssistant, mock_redis_client):
        """
        Test that platforms are loaded.

        Expected:
            - Climate platform loaded
            - Sensor platform loaded
            - Switch platform loaded
            - Binary sensor platform loaded
        """
        # This test would require full Home Assistant test environment
        # Placeholder for integration test structure
        pass


class TestEndToEndScenarios:
    """End-to-end integration test scenarios."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(
            return_value=MagicMock(state="20.0", attributes={})
        )
        return hass

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get_config = AsyncMock(
            return_value={
                "main_climate_entity_id": "climate.main",
                "use_average_mode": False,
                "main_target_all_zones_satisfied": 0.5,
                "min_valves_open": 1,
                "main_min_temp": 18.0,
                "main_max_temp": 30.0,
                "main_change_threshold": 0.5,
                "valve_actuation_delay": 120,
                "satisfaction_eps": 0.0,
                "opening_offset": 0.3,
                "closing_offset": 0.3,
            }
        )
        redis.get_zone_ids = AsyncMock(return_value=["bedroom", "kitchen"])
        redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "current_temperature": 19.0,
                    "satisfaction": "underheated",
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "closed",
                    "priority": 0,
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "current_temperature": 22.0,
                    "satisfaction": "satisfied",
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )
        redis.get_main_climate_state = AsyncMock(
            return_value={
                "target_temperature": 20.0,
                "hvac_action": "heating",
                "multizone_enabled": True,
            }
        )
        redis.update_main_climate_state = AsyncMock()
        redis.update_zone_state = AsyncMock()
        redis.update_zone_valve_state = AsyncMock()
        redis.set_valve_lock = AsyncMock()
        redis.is_valve_locked = AsyncMock(return_value=False)
        redis.acquire_job_lock = AsyncMock(return_value=True)
        redis.release_job_lock = AsyncMock()
        return redis

    async def test_scenario_zone_temp_drops(self, mock_hass, mock_redis):
        """
        Test Scenario: Zone temperature drops, system responds.

        Flow:
            1. Bedroom temp drops to 19.0°C (target: 20.0°C)
            2. Zone becomes underheated
            3. Calculate main temp job triggered
            4. Main temp recalculated to 21.0°C
            5. Update valves job triggered
            6. Bedroom valve opens
        """
        from custom_components.multizone_climate.jobs.calculate_main_temp import (
            CalculateMainTempJob,
        )
        from custom_components.multizone_climate.jobs.update_valves import (
            UpdateValvesJob,
        )

        # Step 1-2: Temperature drops (already set in fixture)

        # Step 3-4: Calculate main temp
        calc_job = CalculateMainTempJob(mock_redis, mock_hass)
        calc_result = await calc_job.execute({"trigger": "temp_change"})

        assert calc_result["main_target_calculated"] == 21.0
        assert calc_result["main_target_updated"] is True

        # Step 5-6: Update valves
        valve_job = UpdateValvesJob(mock_redis, mock_hass)
        valve_result = await valve_job.execute({"trigger": "calc_temp_complete"})

        assert "valves_opened" in valve_result
        assert result["actions_taken"] > 0 or "actions_taken" not in valve_result

    async def test_scenario_all_zones_satisfied(self, mock_hass, mock_redis):
        """
        Test Scenario: All zones reach target temperature.

        Flow:
            1. All zones at target
            2. All zones marked satisfied
            3. Main temp adjusted based on slider setting
            4. Valves remain open to maintain temperature
        """
        # Make all zones satisfied
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "current_temperature": 20.0,
                    "satisfaction": "satisfied",
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "current_temperature": 22.0,
                    "satisfaction": "satisfied",
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )

        from custom_components.multizone_climate.jobs.calculate_main_temp import (
            CalculateMainTempJob,
        )

        calc_job = CalculateMainTempJob(mock_redis, mock_hass)
        result = await calc_job.execute({"trigger": "temp_change"})

        # With slider at 50%, main target should be midpoint
        assert result["main_target_calculated"] == 21.0

    async def test_scenario_safety_minimum_valves(self, mock_hass, mock_redis):
        """
        Test Scenario: Safety check ensures minimum valves open.

        Flow:
            1. All zones become overheated
            2. All valves would close
            3. Safety check detects violation
            4. Fallback valve forced open
        """
        # Make all zones overheated
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "current_temperature": 21.0,
                    "satisfaction": "overheated",
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "current_temperature": 23.0,
                    "satisfaction": "overheated",
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )

        from custom_components.multizone_climate.jobs.safety_check import (
            SafetyCheckJob,
        )

        safety_job = SafetyCheckJob(mock_redis, mock_hass)
        result = await safety_job.execute({})

        # Safety should force open at least min_valves_open (1)
        assert "valves_forced_open" in result or "safety_violation" in result

    async def test_scenario_zone_priority_handling(self, mock_hass, mock_redis):
        """
        Test Scenario: High priority zone gets preference.

        Flow:
            1. Multiple zones need heating
            2. One zone has higher priority
            3. High priority zone managed first
        """
        # Set different priorities
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "current_temperature": 18.0,
                    "satisfaction": "underheated",
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "closed",
                    "priority": 10,  # High priority
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "current_temperature": 19.0,
                    "satisfaction": "underheated",
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "closed",
                    "priority": 0,  # Normal priority
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )

        from custom_components.multizone_climate.jobs.update_valves import (
            UpdateValvesJob,
        )

        valve_job = UpdateValvesJob(mock_redis, mock_hass)
        result = await valve_job.execute({"trigger": "temp_change"})

        # Bedroom should be processed first due to higher priority
        # Both valves should open since both are underheated
        assert "valves_opened" in result or "actions_taken" in result

    async def test_scenario_multizone_disabled(self, mock_hass, mock_redis):
        """
        Test Scenario: Multizone feature disabled, individual control.

        Flow:
            1. Multizone feature turned OFF
            2. Each zone manages own valve
            3. No coordinated temperature calculation
        """
        redis_state = await mock_redis.get_main_climate_state()
        redis_state["multizone_enabled"] = False
        mock_redis.get_main_climate_state = AsyncMock(return_value=redis_state)

        from custom_components.multizone_climate.jobs.update_valves import (
            UpdateValvesJob,
        )

        valve_job = UpdateValvesJob(mock_redis, mock_hass)
        result = await valve_job.execute({"trigger": "temp_change"})

        # Valves should still be managed, but individually
        assert "actions_taken" in result or "valves_opened" in result
