"""Temperature change automation."""

from __future__ import annotations

from typing import Any
import logging
import asyncio
from datetime import timedelta

from homeassistant.core import Event, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..const import JOB_TYPE_CALCULATE_MAIN_TEMP, JOB_TYPE_UPDATE_VALVES

_LOGGER = logging.getLogger(__name__)


class TemperatureChangeAutomation:
    """
    Automation triggered by temperature or target changes.

    Listens for:
    - Zone temperature sensor state changes
    - Zone target temperature changes
    - Main climate temperature changes

    Actions:
    - Enqueue calculate_main_temp job
    - Enqueue update_valves job
    """

    def __init__(self, hass: Any, redis_client: Any) -> None:
        """
        Initialize automation.

        Args:
            hass: Home Assistant instance
            redis_client: Redis client for job queueing
        """
        self.hass = hass
        self.redis_client = redis_client
        self._debounce_task: asyncio.Task | None = None
        self._cancel_listeners: list = []

    async def setup(self) -> None:
        """
        Set up automation listeners.

        Tasks:
            - Register state change listeners for all zone sensors
            - Register target temperature change listeners
            - Set up debouncing (5 seconds)
        """
        zone_ids = await self.redis_client.get_zone_ids()
        sensor_entity_ids = []

        for zone_id in zone_ids:
            zone_state = await self.redis_client.get_zone_state(zone_id)
            if zone_state and "temperature_sensor_entity_id" in zone_state:
                sensor_entity_ids.append(zone_state["temperature_sensor_entity_id"])

        if sensor_entity_ids:
            cancel = async_track_state_change_event(
                self.hass, sensor_entity_ids, self._handle_temperature_change
            )
            self._cancel_listeners.append(cancel)
            _LOGGER.info(
                "Temperature change automation listening to %d sensors",
                len(sensor_entity_ids),
            )

    @callback
    def _handle_temperature_change(self, event: Event) -> None:
        """
        Handle temperature sensor state change.

        Args:
            event: State change event

        Tasks:
            - Debounce event (5 seconds)
            - Enqueue calculate_main_temp job
            - Enqueue update_valves job
        """
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounced_enqueue())

    async def _debounced_enqueue(self) -> None:
        """Debounce wrapper that waits 5 seconds before enqueuing."""
        try:
            await asyncio.sleep(5)
            await self._enqueue_jobs()
        except asyncio.CancelledError:
            pass

    async def _enqueue_jobs(self) -> None:
        """
        Enqueue background jobs.

        Tasks:
            - Create job data dict
            - Enqueue to calculate_main_temp queue
            - Enqueue to update_valves queue
        """
        current_time = self.hass.loop.time()
        job_id_suffix = f"{int(current_time * 1000)}"

        job_data_calc = {
            "job_id": f"calc_temp_auto_{job_id_suffix}",
            "trigger": "temperature_change_automation",
            "enqueued_at": current_time,
        }

        job_data_valve = {
            "job_id": f"update_valves_auto_{job_id_suffix}",
            "trigger": "temperature_change_automation",
            "enqueued_at": current_time,
        }

        await self.redis_client.enqueue_job(JOB_TYPE_CALCULATE_MAIN_TEMP, job_data_calc)
        await self.redis_client.enqueue_job(JOB_TYPE_UPDATE_VALVES, job_data_valve)

        _LOGGER.debug("Enqueued jobs after temperature change")

    async def stop(self) -> None:
        """Stop the automation and cleanup listeners."""
        for cancel in self._cancel_listeners:
            cancel()
        self._cancel_listeners.clear()

        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass
