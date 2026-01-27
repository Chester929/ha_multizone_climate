"""Unit tests for Redis client zone validation."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from custom_components.multizone_climate.core.redis_client import RedisClient


class TestRedisClientValidation:
    """Test the Redis client zone validation logic."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis connection."""
        redis = MagicMock()
        redis.hgetall = AsyncMock()
        redis.rpush = AsyncMock()
        redis.lpos = AsyncMock()
        redis.hset = AsyncMock()
        return redis

    @pytest.fixture
    def redis_client(self, mock_redis):
        """Create Redis client with mock connection."""
        client = RedisClient(host="localhost", port=6379)
        client._redis = mock_redis
        return client

    @pytest.mark.asyncio
    async def test_add_zone_rejects_existing_zone(self, redis_client, mock_redis):
        """Test that add_zone raises ValueError when zone already exists."""
        # Setup: existing zone
        mock_redis.hgetall.return_value = {
            "id": "zone1",
            "name": "Bedroom",
            "temperature_sensor_entity_id": "sensor.bedroom_temp",
        }

        zone_data = {
            "id": "zone1",
            "name": "Duplicate Zone",
            "temperature_sensor_entity_id": "sensor.other_temp",
        }

        # Should raise ValueError
        with pytest.raises(ValueError, match="Zone zone1 already exists"):
            await redis_client.add_zone("zone1", zone_data)

        # Should NOT call rpush or hset
        mock_redis.rpush.assert_not_called()
        mock_redis.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_zone_accepts_new_zone(self, redis_client, mock_redis):
        """Test that add_zone accepts new zones."""
        # Setup: zone doesn't exist
        mock_redis.hgetall.return_value = {}
        mock_redis.lpos.return_value = None  # Not in list

        zone_data = {
            "id": "zone2",
            "name": "Living Room",
            "temperature_sensor_entity_id": "sensor.living_temp",
            "valve_switch_entity_id": "switch.living_valve",
            "target_temperature": 21.0,
        }

        # Should succeed
        await redis_client.add_zone("zone2", zone_data)

        # Should call rpush to add to list
        mock_redis.rpush.assert_called_once()
        # Should call hset to create state
        mock_redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_zone_with_disconnected_redis(self, mock_redis):
        """Test that add_zone handles disconnected Redis gracefully."""
        client = RedisClient(host="localhost", port=6379)
        client._redis = None  # Not connected

        zone_data = {
            "id": "zone1",
            "name": "Test Zone",
        }

        # Should not raise, just log error
        await client.add_zone("zone1", zone_data)
        # No assertions on mock_redis since it's not connected

    @pytest.mark.asyncio
    async def test_add_zone_reraises_value_error(self, redis_client, mock_redis):
        """Test that ValueError is re-raised explicitly."""
        # Setup: existing zone
        mock_redis.hgetall.return_value = {"id": "zone1", "name": "Existing"}

        zone_data = {"id": "zone1", "name": "New"}

        # Should re-raise ValueError (not generic Exception)
        with pytest.raises(ValueError):
            await redis_client.add_zone("zone1", zone_data)

    @pytest.mark.asyncio
    async def test_add_zone_raises_exception_on_redis_error(
        self, redis_client, mock_redis
    ):
        """Test that Redis errors are raised."""
        # Setup: zone doesn't exist but Redis fails
        mock_redis.hgetall.return_value = {}
        mock_redis.lpos.return_value = None
        mock_redis.rpush.side_effect = Exception("Redis connection failed")

        zone_data = {"id": "zone1", "name": "Test"}

        # Should raise the exception
        with pytest.raises(Exception, match="Redis connection failed"):
            await redis_client.add_zone("zone1", zone_data)
