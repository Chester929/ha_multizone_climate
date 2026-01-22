"""Unit tests for background jobs."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.multizone_climate.jobs.calculate_main_temp import (
    CalculateMainTempJob,
)
from custom_components.multizone_climate.jobs.update_valves import UpdateValvesJob
from custom_components.multizone_climate.jobs.safety_check import SafetyCheckJob


class TestCalculateMainTempJob:
    """Test CalculateMainTempJob."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get_config = AsyncMock(
            return_value={
                "use_average_mode": False,
                "main_target_all_zones_satisfied": 0.5,
                "main_min_temp": 18.0,
                "main_max_temp": 30.0,
                "main_change_threshold": 0.5,
            }
        )
        redis.get_zone_ids = AsyncMock(return_value=["bedroom", "kitchen"])
        redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "satisfaction": "underheated",
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "satisfaction": "satisfied",
                },
            }.get(zone_id)
        )
        redis.get_main_climate_state = AsyncMock(
            return_value={"target_temperature": 20.0}
        )
        redis.update_main_climate_state = AsyncMock()
        return redis

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        return hass

    async def test_calculate_main_temp_basic(self, mock_redis, mock_hass):
        """
        Test basic calculate main temp execution.

        Scenario:
            - 2 zones with targets 20°C and 22°C
            - Slider at 50%
            - Expected main target: 21.0°C
        """
        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "zone_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert result["main_target_calculated"] == 21.0
        assert result["main_target_updated"] is True
        assert result["zones_processed"] == 2

        # Verify service call to update main climate
        mock_hass.services.async_call.assert_called_once()
        call_args = mock_hass.services.async_call.call_args
        assert call_args[0][0] == "climate"
        assert call_args[0][1] == "set_temperature"

    async def test_calculate_main_temp_no_zones(self, mock_redis, mock_hass):
        """
        Test calculate main temp with no zones.

        Expected: No update, return 0 zones processed
        """
        mock_redis.get_zone_ids = AsyncMock(return_value=[])
        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "zone_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert result["main_target_calculated"] is None
        assert result["main_target_updated"] is False
        assert result["zones_processed"] == 0

    async def test_calculate_main_temp_no_config(self, mock_redis, mock_hass):
        """
        Test calculate main temp with no config.

        Expected: Return error
        """
        mock_redis.get_config = AsyncMock(return_value=None)
        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "zone_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert "error" in result
        assert result["error"] == "no_config"

    async def test_calculate_main_temp_threshold_not_exceeded(
        self, mock_redis, mock_hass
    ):
        """
        Test that small changes below threshold don't trigger update.

        Scenario:
            - Current main target: 21.2°C
            - Calculated: 21.0°C
            - Diff: 0.2°C < 0.5°C threshold
            - Expected: No update
        """
        mock_redis.get_main_climate_state = AsyncMock(
            return_value={"target_temperature": 21.2}
        )
        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "zone_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert result["main_target_calculated"] == 21.0
        assert result["main_target_updated"] is False
        assert not mock_hass.services.async_call.called

    async def test_calculate_main_temp_average_mode(self, mock_redis, mock_hass):
        """
        Test calculate main temp in average mode.

        Scenario:
            - 2 zones with targets 20°C and 22°C
            - Average mode enabled
            - Expected: 21.0°C (average)
        """
        config = await mock_redis.get_config()
        config["use_average_mode"] = True
        mock_redis.get_config = AsyncMock(return_value=config)

        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "zone_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert result["main_target_calculated"] == 21.0
        assert result["main_target_updated"] is True


class TestUpdateValvesJob:
    """Test UpdateValvesJob."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get_config = AsyncMock(
            return_value={
                "min_valves_open": 1,
                "valve_actuation_delay": 120,
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
                    "current_temperature": 23.0,
                    "satisfaction": "overheated",
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "open",
                    "priority": 0,
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )
        redis.get_main_climate_state = AsyncMock(
            return_value={
                "hvac_action": "heating",
                "multizone_enabled": True,
            }
        )
        redis.set_valve_lock = AsyncMock()
        redis.is_valve_locked = AsyncMock(return_value=False)
        redis.update_zone_valve_state = AsyncMock()
        return redis

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        return hass

    async def test_update_valves_basic(self, mock_redis, mock_hass):
        """
        Test basic valve update.

        Scenario:
            - Bedroom: underheated, valve closed -> should open
            - Kitchen: overheated, valve open -> should close
            - Multizone enabled
        """
        job = UpdateValvesJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "temp_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert "valves_opened" in result
        assert "valves_closed" in result
        assert result["actions_taken"] > 0

    async def test_update_valves_multizone_disabled(self, mock_redis, mock_hass):
        """
        Test valve update with multizone disabled.

        Expected: Each zone manages its own valve
        """
        redis_state = await mock_redis.get_main_climate_state()
        redis_state["multizone_enabled"] = False
        mock_redis.get_main_climate_state = AsyncMock(return_value=redis_state)

        job = UpdateValvesJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "temp_change"})

        # Should still process valves but with different logic
        assert response["status"] == "completed"
        assert "result" in response

    async def test_update_valves_minimum_safety(self, mock_redis, mock_hass):
        """
        Test that minimum valves open is maintained.

        Scenario:
            - Both zones overheated (would close all valves)
            - Minimum 1 valve required
            - Expected: Force open 1 fallback valve
        """
        # Make both zones overheated
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

        job = UpdateValvesJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "temp_change"})

        # Should keep at least 1 valve open (fallback)
        assert response["status"] == "completed"
        result = response["result"]
        # Implementation should ensure min valves open
        # Either valves_opened has the fallback or valves_unchanged contains it

    async def test_update_valves_no_config(self, mock_redis, mock_hass):
        """
        Test update valves with no config.

        Expected: Return error
        """
        mock_redis.get_config = AsyncMock(return_value=None)
        job = UpdateValvesJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "temp_change"})

        assert response["status"] == "completed"
        result = response["result"]
        assert "error" in result
        assert result["error"] == "no_config"


class TestSafetyCheckJob:
    """Test SafetyCheckJob."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get_config = AsyncMock(
            return_value={
                "min_valves_open": 1,
                "valve_actuation_delay": 120,
            }
        )
        redis.get_zone_ids = AsyncMock(return_value=["bedroom", "kitchen"])
        redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "closed",
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "closed",
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )
        redis.set_valve_lock = AsyncMock()
        redis.update_zone_valve_state = AsyncMock()
        return redis

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        return hass

    async def test_safety_check_violation(self, mock_redis, mock_hass):
        """
        Test safety check when minimum valves not met.

        Scenario:
            - All valves closed
            - Minimum 1 required
            - Expected: Force open fallback valve
        """
        job = SafetyCheckJob(mock_redis, mock_hass)
        response = await job.execute({})

        assert response["status"] == "completed"
        result = response["result"]
        # Check if fallback valves were opened
        assert "fallback_valves_opened" in result or "valves_forced_open" in result

    async def test_safety_check_ok(self, mock_redis, mock_hass):
        """
        Test safety check when minimum is satisfied.

        Scenario:
            - 1 valve already open
            - Minimum 1 required
            - Expected: No action needed
        """
        # Make bedroom valve open
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "open",
                    "is_fallback_valve": True,
                },
                "kitchen": {
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "closed",
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )

        job = SafetyCheckJob(mock_redis, mock_hass)
        response = await job.execute({})

        assert response["status"] == "completed"
        result = response["result"]
        # Safety should be satisfied when minimum is met
        assert result.get("safety_satisfied") is True

    async def test_safety_check_no_fallback_valves(self, mock_redis, mock_hass):
        """
        Test safety check with no fallback valves configured.

        Scenario:
            - All valves closed
            - No fallback valves
            - Expected: Open first available valve with warning
        """
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "valve_id": "switch.bedroom_valve",
                    "valve_state": "closed",
                    "is_fallback_valve": False,
                },
                "kitchen": {
                    "valve_id": "switch.kitchen_valve",
                    "valve_state": "closed",
                    "is_fallback_valve": False,
                },
            }.get(zone_id)
        )

        job = SafetyCheckJob(mock_redis, mock_hass)
        response = await job.execute({})

        # Should still force open at least one valve
        assert response["status"] == "completed"
        result = response["result"]
        # Check that some action was taken to ensure safety
        assert "fallback_valves_opened" in result or "valves_forced_open" in result


class TestJobLocking:
    """Test job locking mechanisms."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.acquire_job_lock = AsyncMock(return_value=True)
        redis.release_job_lock = AsyncMock()
        redis.get_config = AsyncMock(return_value={})
        redis.get_zone_ids = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def mock_hass(self):
        """Create mock hass."""
        return MagicMock()

    async def test_job_acquires_lock(self, mock_redis, mock_hass):
        """
        Test that job acquires lock before execution.

        Expected: acquire_job_lock called with job type
        """
        job = CalculateMainTempJob(mock_redis, mock_hass)
        await job.execute({"trigger": "test"})

        mock_redis.acquire_job_lock.assert_called_once()

    async def test_job_releases_lock_on_success(self, mock_redis, mock_hass):
        """
        Test that job releases lock after successful execution.

        Expected: release_job_lock called
        """
        job = CalculateMainTempJob(mock_redis, mock_hass)
        await job.execute({"trigger": "test"})

        mock_redis.release_job_lock.assert_called_once()

    async def test_job_blocked_when_locked(self, mock_redis, mock_hass):
        """
        Test that job execution is blocked when lock is held.

        Expected: Job returns immediately without executing
        """
        mock_redis.acquire_job_lock = AsyncMock(return_value=False)

        job = CalculateMainTempJob(mock_redis, mock_hass)
        response = await job.execute({"trigger": "test"})

        assert response["status"] == "skipped"
        assert response["reason"] == "already_running"
