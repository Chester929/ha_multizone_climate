"""Unit tests for zone persistence atomicity."""

import json
import pytest
from unittest.mock import AsyncMock
from custom_components.multizone_climate.core.redis_client import RedisClient


class TestZonePersistence:
    """Test zone persistence atomicity."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client instance."""
        client = RedisClient(host="localhost", port=6379)
        # Mock the actual Redis connection
        client._redis = AsyncMock()

        return client

    @pytest.mark.asyncio
    async def test_add_zone_atomic_success(self, redis_client):
        """Test that add_zone successfully adds both zone_id and zone_data."""
        zone_id = "test-zone-123"
        zone_data = {
            "id": zone_id,
            "name": "Test Zone",
            "temperature_sensor_entity_id": "sensor.test",
            "valve_switch_entity_id": "switch.test",
        }

        # Mock Redis operations
        redis_client._redis.lpos.return_value = None  # Zone not in list
        redis_client._redis.rpush.return_value = 1
        redis_client._redis.hgetall.return_value = {}  # Zone doesn't exist yet
        redis_client._redis.hset.return_value = None

        # Add zone
        await redis_client.add_zone(zone_id, zone_data)

        # Verify zone was added to list
        redis_client._redis.rpush.assert_called_once_with(
            "multizone:zones", zone_id
        )

        # Verify zone state was saved
        redis_client._redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_zone_atomic_failure_cleanup(self, redis_client):
        """Test that add_zone cleans up zone_id from list if state save fails."""
        zone_id = "test-zone-456"
        zone_data = {
            "id": zone_id,
            "name": "Test Zone",
            "temperature_sensor_entity_id": "sensor.test",
            "valve_switch_entity_id": "switch.test",
        }

        # Mock Redis operations
        redis_client._redis.lpos.return_value = None  # Zone not in list
        redis_client._redis.rpush.return_value = 1  # Successfully added to list
        redis_client._redis.hgetall.return_value = {}  # Zone doesn't exist yet
        redis_client._redis.hset.side_effect = Exception(
            "Redis connection error"
        )  # HSet fails
        redis_client._redis.lrem.return_value = 1  # Cleanup succeeds

        # Attempt to add zone - should fail
        with pytest.raises(Exception, match="Redis connection error"):
            await redis_client.add_zone(zone_id, zone_data)

        # Verify zone was added to list initially
        redis_client._redis.rpush.assert_called_once_with(
            "multizone:zones", zone_id
        )

        # Verify zone state save was attempted
        redis_client._redis.hset.assert_called_once()

        # Verify cleanup was performed - zone_id removed from list
        redis_client._redis.lrem.assert_called_once_with(
            "multizone:zones", 1, zone_id
        )

    @pytest.mark.asyncio
    async def test_set_zone_state_raises_exception(self, redis_client):
        """Test that set_zone_state raises exceptions instead of swallowing them."""
        zone_id = "test-zone-789"
        zone_data = {
            "name": "Test Zone",
            "temperature_sensor_entity_id": "sensor.test",
        }

        # Mock HSet to raise an exception
        redis_client._redis.hset.side_effect = Exception("Connection timeout")

        # Attempt to set zone state - should raise exception
        with pytest.raises(Exception, match="Connection timeout"):
            await redis_client.set_zone_state(zone_id, zone_data)

    @pytest.mark.asyncio
    async def test_set_zone_state_forces_id_match(self, redis_client):
        """Test that set_zone_state forces 'id' field to match zone_id parameter."""
        zone_id = "correct-zone-id"
        zone_data = {
            "id": "wrong-zone-id",  # Intentionally wrong ID
            "name": "Test Zone",
            "temperature_sensor_entity_id": "sensor.test",
        }

        # Mock Redis operations
        redis_client._redis.hset.return_value = None
        redis_client._redis.hgetall.return_value = {}

        # Set zone state
        await redis_client.set_zone_state(zone_id, zone_data)

        # Verify hset was called
        redis_client._redis.hset.assert_called_once()
        
        # Get the actual data that was written
        call_args = redis_client._redis.hset.call_args
        written_data = call_args[1]['mapping']
        
        # Verify the 'id' field was forced to match zone_id parameter
        assert json.loads(written_data['id']) == zone_id, "ID field should be forced to match zone_id parameter"

    @pytest.mark.asyncio
    async def test_add_zone_already_exists(self, redis_client):
        """Test that add_zone raises ValueError if zone already exists in hash."""
        zone_id = "existing-zone"
        zone_data = {"name": "Existing Zone"}

        # Mock zone already exists (hash exists)
        redis_client._redis.hgetall.return_value = {"name": "Existing Zone"}

        # Attempt to add existing zone - should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            await redis_client.add_zone(zone_id, zone_data)

        # Verify no attempt was made to check list, add to list, or save state
        redis_client._redis.lpos.assert_not_called()
        redis_client._redis.rpush.assert_not_called()
        redis_client._redis.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_zone_id_already_in_list(self, redis_client):
        """Test that add_zone raises ValueError if zone_id already in zones list."""
        zone_id = "test-zone-in-list"
        zone_data = {"name": "Test Zone"}

        # Mock zone not in hash but already in list (orphaned list entry)
        redis_client._redis.hgetall.return_value = {}  # Zone doesn't exist in hash
        redis_client._redis.lpos.return_value = 0  # Zone exists in list at position 0

        # Attempt to add zone - should raise ValueError
        with pytest.raises(ValueError, match="already exists in zones list"):
            await redis_client.add_zone(zone_id, zone_data)

        # Verify we didn't try to add to list or save state
        redis_client._redis.rpush.assert_not_called()
        redis_client._redis.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_zone_redis_not_connected(self, redis_client):
        """Test that add_zone raises RuntimeError if Redis is not connected."""
        zone_id = "test-zone"
        zone_data = {"name": "Test Zone"}

        # Mock Redis not connected
        redis_client._redis = None

        # Attempt to add zone - should raise RuntimeError
        with pytest.raises(RuntimeError, match="not connected"):
            await redis_client.add_zone(zone_id, zone_data)

    @pytest.mark.asyncio
    async def test_set_zone_state_empty_data(self, redis_client):
        """Test that set_zone_state raises ValueError for empty zone data."""
        zone_id = "test-zone"
        zone_data = {}  # Empty data

        # Attempt to set empty zone state - should raise ValueError
        with pytest.raises(ValueError, match="Cannot set empty zone state"):
            await redis_client.set_zone_state(zone_id, zone_data)

    @pytest.mark.asyncio
    async def test_set_zone_state_redis_not_connected(self, redis_client):
        """Test that set_zone_state raises RuntimeError if Redis is not connected."""
        zone_id = "test-zone"
        zone_data = {"name": "Test Zone"}

        # Mock Redis not connected
        redis_client._redis = None

        # Attempt to set zone state - should raise RuntimeError
        with pytest.raises(RuntimeError, match="not connected"):
            await redis_client.set_zone_state(zone_id, zone_data)

    @pytest.mark.asyncio
    async def test_add_zone_cleanup_failure(self, redis_client):
        """Test that errors are logged if cleanup fails during add_zone rollback."""
        zone_id = "test-zone"
        zone_data = {"name": "Test Zone"}

        # Mock Redis operations
        redis_client._redis.lpos.return_value = None  # Zone not in list
        redis_client._redis.rpush.return_value = 1  # Successfully added to list
        redis_client._redis.hgetall.return_value = {}  # Zone doesn't exist yet
        redis_client._redis.hset.side_effect = Exception("State save failed")
        redis_client._redis.lrem.side_effect = Exception("Cleanup failed")

        # Attempt to add zone - should fail with original state save error
        with pytest.raises(Exception, match="State save failed"):
            await redis_client.add_zone(zone_id, zone_data)

        # Verify cleanup was attempted even though it failed
        redis_client._redis.lrem.assert_called_once()
