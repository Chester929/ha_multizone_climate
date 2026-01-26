"""Safety timer automation."""

from __future__ import annotations

from typing import Any, Callable
import logging
from datetime import timedelta, datetime

from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)


class SafetyTimerAutomation:
    """
    Timer-based safety check automation.

    Runs periodically to ensure minimum valves are open.
    Interval: valve_actuation_delay / 2 (default: 60 seconds)
    """

    def __init__(self, hass: Any, redis_client: Any, safety_check_job: Any) -> None:
        """
        Initialize safety timer.

        Args:
            hass: Home Assistant instance
            redis_client: Redis client
            safety_check_job: SafetyCheckJob instance
        """
        self.hass = hass
        self.redis_client = redis_client
        self.safety_check_job = safety_check_job
        self._cancel_timer: Callable[[], None] | None = None

    async def setup(self, interval: int) -> None:
        """
        Set up periodic timer.

        Args:
            interval: Timer interval in seconds

        Tasks:
            - Register async_track_time_interval
            - Store cancel handle
        """
        safe_interval = max(interval, 60)

        self._cancel_timer = async_track_time_interval(
            self.hass, self._execute_safety_check, timedelta(seconds=safe_interval)
        )

        _LOGGER.info(
            "Safety timer automation started with interval %d seconds", safe_interval
        )

    async def _execute_safety_check(self, now: datetime) -> None:
        """
        Execute safety check job.

        Args:
            now: Current time

        Tasks:
            - Execute safety_check_job directly (not queued)
        """
        try:
            job_data = {
                "job_id": f"safety_check_timer_{int(self.hass.loop.time() * 1000)}",
                "trigger": "safety_timer_automation",
                "enqueued_at": self.hass.loop.time(),
            }

            await self.safety_check_job.execute(job_data)
            _LOGGER.debug("Safety check executed at %s", now)
        except Exception as err:
            _LOGGER.error("Error executing safety check: %s", err, exc_info=True)

    async def stop(self) -> None:
        """
        Stop the timer.

        Tasks:
            - Cancel timer
        """
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
            _LOGGER.info("Safety timer automation stopped")
