"""Base class for background jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
import logging
import uuid

_LOGGER = logging.getLogger(__name__)


class BaseJob(ABC):
    """
    Base class for all background jobs.

    Provides:
    - Job identification
    - Status tracking
    - Job locking via Redis
    - Error handling
    - Execution lifecycle management
    """

    def __init__(
        self,
        job_type: str,
        redis_client: Any,
        hass: Any,
    ) -> None:
        """
        Initialize base job.

        Args:
            job_type: Type identifier for this job
            redis_client: Redis client for locking and status
            hass: Home Assistant instance
        """
        self.job_type = job_type
        self.redis_client = redis_client
        self.hass = hass
        self.job_id = f"{job_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def execute(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the job with locking and status tracking.

        Args:
            job_data: Job parameters

        Returns:
            dict: Job execution result

        Lifecycle:
            1. Try to acquire job lock
            2. If locked, return (another instance running)
            3. Set job status to "running"
            4. Execute job logic (implemented by subclass)
            5. Set job status to "completed" or "failed"
            6. Release job lock
            7. Return result
        """
        started_at = datetime.now().isoformat()

        # Try to acquire lock
        lock_acquired = await self._acquire_lock()
        if not lock_acquired:
            _LOGGER.debug("Job %s already running, skipping execution", self.job_type)
            return {"status": "skipped", "reason": "already_running"}

        try:
            # Update status to "running"
            await self._update_status("running")

            # Execute job logic
            result = await self._execute_impl(job_data)

            # Update status to "completed"
            completed_at = datetime.now().isoformat()
            await self._update_status(
                "completed",
                {
                    "result": result,
                    "completed_at": completed_at,
                    "started_at": started_at,
                },
            )

            return {"status": "completed", "result": result}

        except Exception as err:
            # Update status to "failed"
            failed_at = datetime.now().isoformat()
            _LOGGER.error("Job %s failed: %s", self.job_type, err, exc_info=True)

            await self._update_status(
                "failed",
                {
                    "error": str(err),
                    "failed_at": failed_at,
                    "started_at": started_at,
                },
            )

            return {"status": "failed", "error": str(err)}

        finally:
            # Always release lock
            await self._release_lock()

    @abstractmethod
    async def _execute_impl(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute job logic (implemented by subclasses).

        Args:
            job_data: Job parameters

        Returns:
            dict: Job result

        Raises:
            Exception: If job execution fails
        """
        pass

    async def _acquire_lock(self, timeout: int = 60) -> bool:
        """
        Try to acquire job lock.

        Args:
            timeout: Lock timeout in seconds

        Returns:
            bool: True if acquired, False if already locked
        """
        return bool(await self.redis_client.acquire_job_lock(self.job_type, timeout))

    async def _release_lock(self) -> None:
        """Release job lock."""
        await self.redis_client.release_job_lock(self.job_type)

    async def _update_status(
        self, status: str, result: dict[str, Any] | None = None
    ) -> None:
        """
        Update job status in Redis.

        Args:
            status: Job status (running/completed/failed)
            result: Job result data
        """
        status_dict = {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if result:
            status_dict.update(result)

        await self.redis_client.set_job_status(self.job_id, status_dict)
