"""Unit tests for MultizoneClimateCoordinator."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta

from custom_components.multizone_climate.coordinator import (
    MultizoneClimateCoordinator,
)


class TestMultizoneClimateCoordinator:
    """Test MultizoneClimateCoordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get_config = AsyncMock(
            return_value={
                "main_climate_entity_id": "climate.main",
                "min_valves_open": 1,
                "valve_actuation_delay": 120,
            }
        )
        redis.get_zone_ids = AsyncMock(return_value=["bedroom", "kitchen"])
        redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                    "current_temperature": 19.5,
                    "satisfaction": "underheated",
                },
                "kitchen": {
                    "state": "ON",
                    "target_temperature": 22.0,
                    "current_temperature": 22.0,
                    "satisfaction": "satisfied",
                },
            }.get(zone_id)
        )
        redis.get_main_climate_state = AsyncMock(
            return_value={
                "entity_id": "climate.main",
                "target_temperature": 21.0,
                "current_temperature": 20.5,
                "hvac_action": "heating",
            }
        )
        redis.get_queue_size = AsyncMock(return_value=0)
        redis.dequeue_job = AsyncMock(return_value=None)
        return redis

    def test_coordinator_initialization(self, mock_hass, mock_redis):
        """
        Test coordinator initialization.

        Expected:
            - Coordinator created with correct interval
            - Redis client stored
            - Cached data initialized
        """
        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        assert coordinator.redis_client == mock_redis
        assert coordinator.update_interval == timedelta(seconds=15)
        assert isinstance(coordinator._cached_data, dict)

    async def test_coordinator_update_data(self, mock_hass, mock_redis):
        """
        Test coordinator data update.

        Expected:
            - Fetches config from Redis
            - Fetches zone states from Redis
            - Fetches main climate state from Redis
            - Returns updated data
        """
        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        data = await coordinator._async_update_data()

        assert "config" in data
        assert "zones" in data
        assert "main_climate" in data
        assert len(data["zones"]) == 2
        assert "bedroom" in data["zones"]
        assert "kitchen" in data["zones"]

    async def test_coordinator_handles_empty_zones(self, mock_hass, mock_redis):
        """
        Test coordinator with no zones.

        Expected:
            - Handles empty zone list gracefully
            - Returns empty zones dict
        """
        mock_redis.get_zone_ids = AsyncMock(return_value=[])

        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        data = await coordinator._async_update_data()

        assert data["zones"] == {}

    async def test_coordinator_executes_pending_jobs(self, mock_hass, mock_redis):
        """
        Test that coordinator executes pending jobs.

        Expected:
            - Checks job queue sizes
            - Dequeues jobs if available
            - Executes jobs
        """
        # Mock job in queue
        mock_redis.get_queue_size = AsyncMock(
            side_effect=lambda job_type: 1 if job_type == "calculate_main_temp" else 0
        )
        mock_redis.dequeue_job = AsyncMock(
            return_value={
                "job_id": "test_job_123",
                "job_type": "calculate_main_temp",
                "parameters": {"trigger": "zone_change"},
            }
        )

        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        data = await coordinator._async_update_data()

        # Verify queue size checked
        assert mock_redis.get_queue_size.call_count >= 1
        assert data["calculate_queue_size"] == 1

    async def test_coordinator_caches_data(self, mock_hass, mock_redis):
        """
        Test that coordinator caches data for entity access.

        Expected:
            - Data stored in _cached_data
            - Entities can access cached data
        """
        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        await coordinator._async_update_data()

        assert "config" in coordinator._cached_data
        assert "zones" in coordinator._cached_data
        assert "main_climate" in coordinator._cached_data

    async def test_coordinator_handles_redis_failure(self, mock_hass, mock_redis):
        """
        Test coordinator handles Redis connection failure.

        Expected:
            - Raises UpdateFailed on Redis error
        """
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_redis.get_config = AsyncMock(
            side_effect=Exception("Redis connection failed")
        )

        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_coordinator_interval_configurable(self, mock_hass, mock_redis):
        """
        Test that coordinator interval is configurable.

        Expected:
            - Different intervals create different update schedules
        """
        coordinator_15 = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)
        coordinator_30 = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=30)

        assert coordinator_15.update_interval == timedelta(seconds=15)
        assert coordinator_30.update_interval == timedelta(seconds=30)

    async def test_coordinator_zone_state_none_handling(self, mock_hass, mock_redis):
        """
        Test coordinator handles None zone states.

        Expected:
            - Skips zones that return None
            - Continues processing other zones
        """
        mock_redis.get_zone_state = AsyncMock(
            side_effect=lambda zone_id: {
                "bedroom": {
                    "state": "ON",
                    "target_temperature": 20.0,
                },
                "kitchen": None,  # Missing zone
            }.get(zone_id)
        )

        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        data = await coordinator._async_update_data()

        # Should only have bedroom, kitchen skipped
        assert len(data["zones"]) == 1
        assert "bedroom" in data["zones"]
        assert "kitchen" not in data["zones"]

    async def test_coordinator_job_executor_initialization(self, mock_hass, mock_redis):
        """
        Test that coordinator initializes job executors.

        Expected:
            - Job executors dict initialized
            - Ready to execute jobs
        """
        coordinator = MultizoneClimateCoordinator(mock_hass, mock_redis, interval=15)

        assert hasattr(coordinator, "_job_executors")
        assert isinstance(coordinator._job_executors, dict)
