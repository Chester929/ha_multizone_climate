"""Data update coordinator for Multizone Climate."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_COORDINATOR_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateCoordinator(DataUpdateCoordinator):
    """
    Coordinator to manage data updates and job execution.

    Runs every 15 seconds (configurable) to:
    - Fetch latest data from Redis
    - Update sensor states
    - Dequeue and execute background jobs
    """

    def __init__(
        self,
        hass: HomeAssistant,
        redis_client: Any,
        interval: int = DEFAULT_COORDINATOR_INTERVAL,
    ) -> None:
        """
        Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            redis_client: Redis client instance for data access
            interval: Update interval in seconds (default: 15)
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.redis_client = redis_client
        self._cached_data: dict[str, Any] = {}
        self._job_executors: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Fetch data from Redis and execute pending jobs.

        Returns:
            dict: Updated data from Redis

        Tasks:
            1. Fetch global config from Redis
            2. Fetch all zone states from Redis
            3. Fetch main climate state from Redis
            4. Update sensor entities (only if changed)
            5. Dequeue calculate_main_temp job (if any and lock available)
            6. Execute calculate_main_temp job
            7. Dequeue update_valves job (if any and lock available)
            8. Execute update_valves job

        Raises:
            UpdateFailed: If data fetch or job execution fails
        """
        try:
            # Fetch global config from Redis
            config = await self.redis_client.get_config()

            # Fetch all zone states from Redis
            zone_ids = await self.redis_client.get_zone_ids()
            zones = {}
            for zone_id in zone_ids:
                zone_state = await self.redis_client.get_zone_state(zone_id)
                if zone_state:
                    zones[zone_id] = zone_state

            # Fetch main climate state from Redis
            main_climate = await self.redis_client.get_main_climate_state()

            # Fetch job queue sizes
            calculate_queue_size = await self.redis_client.get_queue_size(
                "calculate_main_temp"
            )
            valve_queue_size = await self.redis_client.get_queue_size("update_valves")

            # Store in cached data for entity access
            self._cached_data = {
                "config": config,
                "zones": zones,
                "main_climate": main_climate,
                "calculate_queue_size": calculate_queue_size,
                "valve_queue_size": valve_queue_size,
            }

            # Dequeue and execute calculate_main_temp job if available
            await self.async_dequeue_and_execute_job("calculate_main_temp")

            # Dequeue and execute update_valves job if available
            await self.async_dequeue_and_execute_job("update_valves")

            return self._cached_data

        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}") from err

    async def async_dequeue_and_execute_job(self, job_type: str) -> None:
        """
        Dequeue and execute a background job.

        Args:
            job_type: Type of job (calculate_main_temp, update_valves)

        Tasks:
            - Check if job is in queue
            - Try to acquire job lock
            - If acquired, dequeue and execute job
            - Release lock when done
            - Update job status in Redis
        """
        # Try to acquire job lock first (non-blocking check)
        lock_acquired = await self.redis_client.acquire_job_lock(job_type, timeout=60)
        if not lock_acquired:
            _LOGGER.debug(
                "Job %s already running, skipping dequeue",
                job_type,
            )
            return

        try:
            # Dequeue job from queue
            job_data = await self.redis_client.dequeue_job(job_type)
            if not job_data:
                # No job in queue
                return

            _LOGGER.debug("Dequeued job %s: %s", job_type, job_data)

            # Execute job based on type
            if job_type == "calculate_main_temp":
                await self.async_execute_calculate_main_temp(job_data)
            elif job_type == "update_valves":
                await self.async_execute_update_valves(job_data)
            else:
                _LOGGER.warning("Unknown job type: %s", job_type)

        except Exception as err:
            _LOGGER.error(
                "Error executing job %s: %s",
                job_type,
                err,
                exc_info=True,
            )
        finally:
            # Always release lock
            await self.redis_client.release_job_lock(job_type)

    async def async_execute_calculate_main_temp(self, job_data: dict) -> None:
        """
        Execute calculate main target temperature job.

        Args:
            job_data: Job parameters and context

        Tasks:
            - Fetch current zone states
            - Call core algorithm to calculate main target
            - Update main climate entity if threshold exceeded
            - Update job status
        """
        from .jobs.calculate_main_temp import CalculateMainTempJob

        # Get or create job executor
        if "calculate_main_temp" not in self._job_executors:
            self._job_executors["calculate_main_temp"] = CalculateMainTempJob(
                self.redis_client,
                self.hass,
            )

        job_executor = self._job_executors["calculate_main_temp"]

        # Execute job (uses public execute method with internal locking)
        result = await job_executor.execute(job_data)

        _LOGGER.debug("Calculate main temp job result: %s", result)

    async def async_execute_update_valves(self, job_data: dict) -> None:
        """
        Execute update valves job.

        Args:
            job_data: Job parameters and context

        Tasks:
            - Fetch current zone states
            - Call core algorithm to determine valve actions
            - Execute valve open/close commands
            - Set valve locks
            - Update zone states in Redis
        """
        from .jobs.update_valves import UpdateValvesJob

        # Get or create job executor
        if "update_valves" not in self._job_executors:
            self._job_executors["update_valves"] = UpdateValvesJob(
                self.redis_client,
                self.hass,
            )

        job_executor = self._job_executors["update_valves"]

        # Execute job (uses public execute method with internal locking)
        result = await job_executor.execute(job_data)

        _LOGGER.debug("Update valves job result: %s", result)

    def get_zone_data(self, zone_id: str) -> dict[str, Any] | None:
        """
        Get cached zone data.

        Args:
            zone_id: Zone identifier

        Returns:
            dict: Zone data or None if not found
        """
        if not self._cached_data or "zones" not in self._cached_data:
            return None

        return self._cached_data["zones"].get(zone_id)

    def get_main_climate_data(self) -> dict[str, Any] | None:
        """
        Get cached main climate data.

        Returns:
            dict: Main climate data or None if not available
        """
        if not self._cached_data or "main_climate" not in self._cached_data:
            return None

        return self._cached_data.get("main_climate")

    def get_config(self) -> dict[str, Any] | None:
        """
        Get cached global configuration.

        Returns:
            dict: Global configuration or None if not available
        """
        if not self._cached_data or "config" not in self._cached_data:
            return None

        return self._cached_data.get("config")
