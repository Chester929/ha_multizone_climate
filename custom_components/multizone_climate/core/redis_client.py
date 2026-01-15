"""Redis client for Multizone Climate integration."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

_LOGGER = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client for storing and retrieving multizone climate data.

    Manages connections and CRUD operations for:
    - Global configuration
    - Zone states
    - Main climate state
    - Job queues
    - Valve locks
    - Job locks
    - Job status
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str | None = None,
        db: int = 0,
        key_prefix: str = "ha_multizone",
    ) -> None:
        """
        Initialize Redis client.

        Args:
            host: Redis server hostname
            port: Redis server port
            password: Redis password (optional)
            db: Redis database number
            key_prefix: Prefix for all Redis keys
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.key_prefix = key_prefix
        self._redis: aioredis.Redis | None = None
        self._pool: aioredis.ConnectionPool | None = None

    async def connect(self) -> None:
        """
        Establish connection to Redis server.

        Raises:
            ConnectionError: If connection fails

        Tasks:
            - Create connection pool
            - Test connection
            - Initialize schema if needed
        """
        try:
            self._pool = aioredis.ConnectionPool(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                max_connections=10,
            )
            self._redis = aioredis.Redis(connection_pool=self._pool)

            # Test connection
            await self._redis.ping()
            _LOGGER.info("Connected to Redis at %s:%s", self.host, self.port)

            # Initialize config key if it doesn't exist
            config_key = self._get_key("config")
            if not await self._redis.exists(config_key):
                _LOGGER.debug("Initializing Redis config key")
                await self._redis.hset(config_key, mapping={})

        except Exception as err:
            _LOGGER.error("Failed to connect to Redis: %s", err)
            raise ConnectionError(f"Redis connection failed: {err}") from err

    async def disconnect(self) -> None:
        """
        Close connection to Redis server.

        Tasks:
            - Close connection pool
            - Clean up resources
        """
        if self._redis:
            await self._redis.close()
            _LOGGER.info("Disconnected from Redis")
        if self._pool:
            await self._pool.disconnect()
        self._redis = None
        self._pool = None

    def _get_key(self, key: str) -> str:
        """Generate a Redis key with the configured prefix."""
        return f"{self.key_prefix}:{key}"

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to JSON string for Redis storage."""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def _deserialize_value(self, value: str | None) -> Any:
        """Deserialize a JSON string from Redis storage."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def get_config(self) -> dict[str, Any]:
        """
        Get global configuration from Redis.

        Returns:
            dict: Global configuration parameters

        Redis Key: {prefix}:config
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return {}

        try:
            config_key = self._get_key("config")
            config_data = await self._redis.hgetall(config_key)

            if not config_data:
                return {}

            # Deserialize JSON values
            result = {}
            for key, value in config_data.items():
                result[key] = self._deserialize_value(value)

            return result
        except Exception as err:
            _LOGGER.error("Failed to get config: %s", err)
            return {}

    async def set_config(self, config: dict[str, Any]) -> None:
        """
        Store global configuration in Redis.

        Args:
            config: Configuration dictionary to store

        Redis Key: {prefix}:config
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            config_key = self._get_key("config")

            # Serialize values to JSON
            serialized_config = {
                key: self._serialize_value(value) for key, value in config.items()
            }

            if serialized_config:
                await self._redis.hset(config_key, mapping=serialized_config)
                _LOGGER.debug("Updated config in Redis")
            else:
                _LOGGER.warning("Attempted to set empty config")
        except Exception as err:
            _LOGGER.error("Failed to set config: %s", err)

    async def get_zone_ids(self) -> list[str]:
        """
        Get list of all zone IDs.

        Returns:
            list: List of zone identifiers

        Redis Key: {prefix}:zones
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return []

        try:
            zones_key = self._get_key("zones")
            zone_ids = await self._redis.lrange(zones_key, 0, -1)
            return zone_ids if zone_ids else []
        except Exception as err:
            _LOGGER.error("Failed to get zone IDs: %s", err)
            return []

    async def get_zone_state(self, zone_id: str) -> dict[str, Any] | None:
        """
        Get state for a specific zone.

        Args:
            zone_id: Zone identifier

        Returns:
            dict: Zone state or None if not found

        Redis Key: {prefix}:zone:{zone_id}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return None

        try:
            zone_key = self._get_key(f"zone:{zone_id}")
            zone_data = await self._redis.hgetall(zone_key)

            if not zone_data:
                return None

            # Deserialize JSON values
            result = {}
            for key, value in zone_data.items():
                result[key] = self._deserialize_value(value)

            return result
        except Exception as err:
            _LOGGER.error("Failed to get zone state for %s: %s", zone_id, err)
            return None

    async def set_zone_state(self, zone_id: str, state: dict[str, Any]) -> None:
        """
        Store or update zone state.

        Args:
            zone_id: Zone identifier
            state: Zone state dictionary

        Redis Key: {prefix}:zone:{zone_id}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            zone_key = self._get_key(f"zone:{zone_id}")

            # Serialize values to JSON
            serialized_state = {
                key: self._serialize_value(value) for key, value in state.items()
            }

            if serialized_state:
                await self._redis.hset(zone_key, mapping=serialized_state)
                _LOGGER.debug("Updated zone state for %s", zone_id)
            else:
                _LOGGER.warning("Attempted to set empty zone state for %s", zone_id)
        except Exception as err:
            _LOGGER.error("Failed to set zone state for %s: %s", zone_id, err)

    async def add_zone(self, zone_id: str, zone_data: dict[str, Any]) -> None:
        """
        Add a new zone.

        Args:
            zone_id: Zone identifier
            zone_data: Zone configuration and state

        Tasks:
            - Add zone_id to zones list
            - Create zone state hash
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            zones_key = self._get_key("zones")

            # Check if zone already exists in list
            existing_zones = await self._redis.lrange(zones_key, 0, -1)
            if zone_id not in existing_zones:
                await self._redis.rpush(zones_key, zone_id)
                _LOGGER.debug("Added zone %s to zones list", zone_id)

            # Create zone state
            await self.set_zone_state(zone_id, zone_data)
            _LOGGER.info("Added zone %s", zone_id)
        except Exception as err:
            _LOGGER.error("Failed to add zone %s: %s", zone_id, err)

    async def remove_zone(self, zone_id: str) -> None:
        """
        Remove a zone.

        Args:
            zone_id: Zone identifier

        Tasks:
            - Remove from zones list
            - Delete zone state hash
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            zones_key = self._get_key("zones")
            zone_key = self._get_key(f"zone:{zone_id}")

            # Remove from zones list
            await self._redis.lrem(zones_key, 0, zone_id)

            # Delete zone state hash
            await self._redis.delete(zone_key)

            _LOGGER.info("Removed zone %s", zone_id)
        except Exception as err:
            _LOGGER.error("Failed to remove zone %s: %s", zone_id, err)

    async def get_main_climate_state(self) -> dict[str, Any]:
        """
        Get main climate entity state.

        Returns:
            dict: Main climate state

        Redis Key: {prefix}:main_climate
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return {}

        try:
            main_climate_key = self._get_key("main_climate")
            climate_data = await self._redis.hgetall(main_climate_key)

            if not climate_data:
                return {}

            # Deserialize JSON values
            result = {}
            for key, value in climate_data.items():
                result[key] = self._deserialize_value(value)

            return result
        except Exception as err:
            _LOGGER.error("Failed to get main climate state: %s", err)
            return {}

    async def set_main_climate_state(self, state: dict[str, Any]) -> None:
        """
        Store main climate entity state.

        Args:
            state: Main climate state

        Redis Key: {prefix}:main_climate
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            main_climate_key = self._get_key("main_climate")

            # Serialize values to JSON
            serialized_state = {
                key: self._serialize_value(value) for key, value in state.items()
            }

            if serialized_state:
                await self._redis.hset(main_climate_key, mapping=serialized_state)
                _LOGGER.debug("Updated main climate state")
            else:
                _LOGGER.warning("Attempted to set empty main climate state")
        except Exception as err:
            _LOGGER.error("Failed to set main climate state: %s", err)

    async def enqueue_job(self, job_type: str, job_data: dict[str, Any]) -> None:
        """
        Add a job to the queue.

        Args:
            job_type: Job type (calculate_main_temp, update_valves)
            job_data: Job parameters

        Redis Key: {prefix}:queue:{job_type}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            queue_key = self._get_key(f"queue:{job_type}")
            job_json = json.dumps(job_data)

            # LPUSH for FIFO (left push, right pop)
            await self._redis.lpush(queue_key, job_json)
            _LOGGER.debug("Enqueued job type %s", job_type)
        except Exception as err:
            _LOGGER.error("Failed to enqueue job %s: %s", job_type, err)

    async def dequeue_job(self, job_type: str) -> dict[str, Any] | None:
        """
        Remove and return next job from queue.

        Args:
            job_type: Job type queue to dequeue from

        Returns:
            dict: Job data or None if queue empty

        Redis Key: {prefix}:queue:{job_type}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return None

        try:
            queue_key = self._get_key(f"queue:{job_type}")

            # RPOP for FIFO (left push, right pop)
            job_json = await self._redis.rpop(queue_key)

            if job_json:
                job_data = json.loads(job_json)
                _LOGGER.debug("Dequeued job type %s", job_type)
                return job_data

            return None
        except Exception as err:
            _LOGGER.error("Failed to dequeue job %s: %s", job_type, err)
            return None

    async def acquire_job_lock(self, job_type: str, timeout: int = 60) -> bool:
        """
        Try to acquire a job lock.

        Args:
            job_type: Job type to lock
            timeout: Lock timeout in seconds

        Returns:
            bool: True if lock acquired, False otherwise

        Redis Key: {prefix}:joblock:{job_type}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return False

        try:
            lock_key = self._get_key(f"joblock:{job_type}")
            now = time.time()

            # SET NX (set if not exists) with expiration for atomic lock
            success = await self._redis.set(lock_key, str(now), nx=True, ex=timeout)

            if success:
                _LOGGER.debug("Acquired job lock for %s", job_type)
            else:
                _LOGGER.debug(
                    "Failed to acquire job lock for %s (already locked)", job_type
                )

            return bool(success)
        except Exception as err:
            _LOGGER.error("Failed to acquire job lock for %s: %s", job_type, err)
            return False

    async def release_job_lock(self, job_type: str) -> None:
        """
        Release a job lock.

        Args:
            job_type: Job type to unlock

        Redis Key: {prefix}:joblock:{job_type}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            lock_key = self._get_key(f"joblock:{job_type}")
            await self._redis.delete(lock_key)
            _LOGGER.debug("Released job lock for %s", job_type)
        except Exception as err:
            _LOGGER.error("Failed to release job lock for %s: %s", job_type, err)

    async def set_valve_lock(
        self, valve_id: str, locked_until: float, reason: str = ""
    ) -> None:
        """
        Set a valve lock to prevent re-actuation.

        Args:
            valve_id: Valve switch entity ID
            locked_until: Timestamp when lock expires
            reason: Reason for lock (for debugging)

        Redis Key: {prefix}:valvelock:{valve_id}
        TTL: Calculated from locked_until
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            lock_key = self._get_key(f"valvelock:{valve_id}")
            now = time.time()
            ttl = int(locked_until - now)

            if ttl <= 0:
                _LOGGER.warning("Valve lock TTL <= 0 for %s, skipping", valve_id)
                return

            lock_data = {
                "locked_until": locked_until,
                "reason": reason,
                "timestamp": now,
            }

            # Store lock with TTL
            await self._redis.set(lock_key, json.dumps(lock_data), ex=ttl)
            _LOGGER.debug(
                "Set valve lock for %s (TTL: %ds, reason: %s)", valve_id, ttl, reason
            )
        except Exception as err:
            _LOGGER.error("Failed to set valve lock for %s: %s", valve_id, err)

    async def is_valve_locked(self, valve_id: str) -> bool:
        """
        Check if a valve is locked.

        Args:
            valve_id: Valve switch entity ID

        Returns:
            bool: True if locked, False otherwise

        Redis Key: {prefix}:valvelock:{valve_id}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return False

        try:
            lock_key = self._get_key(f"valvelock:{valve_id}")
            exists = await self._redis.exists(lock_key)
            return bool(exists)
        except Exception as err:
            _LOGGER.error("Failed to check valve lock for %s: %s", valve_id, err)
            return False

    async def set_job_status(self, job_id: str, status: dict[str, Any]) -> None:
        """
        Store job execution status.

        Args:
            job_id: Unique job identifier
            status: Job status data

        Redis Key: {prefix}:jobstatus:{job_id}
        TTL: Configured job_status_ttl
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return

        try:
            status_key = self._get_key(f"jobstatus:{job_id}")

            # Serialize values to JSON
            serialized_status = {
                key: self._serialize_value(value) for key, value in status.items()
            }

            if serialized_status:
                # Store job status hash
                await self._redis.hset(status_key, mapping=serialized_status)

                # Set TTL (default 900 seconds = 15 minutes)
                ttl = 900
                await self._redis.expire(status_key, ttl)

                _LOGGER.debug("Set job status for %s (TTL: %ds)", job_id, ttl)
            else:
                _LOGGER.warning("Attempted to set empty job status for %s", job_id)
        except Exception as err:
            _LOGGER.error("Failed to set job status for %s: %s", job_id, err)

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job execution status.

        Args:
            job_id: Job identifier

        Returns:
            dict: Job status or None if not found

        Redis Key: {prefix}:jobstatus:{job_id}
        """
        if not self._redis:
            _LOGGER.error("Redis client not connected")
            return None

        try:
            status_key = self._get_key(f"jobstatus:{job_id}")
            status_data = await self._redis.hgetall(status_key)

            if not status_data:
                return None

            # Deserialize JSON values
            result = {}
            for key, value in status_data.items():
                result[key] = self._deserialize_value(value)

            return result
        except Exception as err:
            _LOGGER.error("Failed to get job status for %s: %s", job_id, err)
            return None
