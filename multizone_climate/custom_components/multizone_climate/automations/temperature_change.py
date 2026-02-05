"""Temperature change automation."""

from __future__ import annotations

from typing import Any
import logging
import asyncio

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
        self._update_main_climate_task: asyncio.Task | None = None
        self._cancel_listeners: list = []

    async def setup(self) -> None:
        """
        Set up automation listeners.

        Tasks:
            - Register state change listeners for all zone sensors
            - Register state change listener for main climate entity
            - Register target temperature change listeners
            - Set up debouncing (5 seconds)
        """
        zone_ids = await self.redis_client.get_zone_ids()
        sensor_entity_ids: list[str] = []

        for zone_id in zone_ids:
            zone_state = await self.redis_client.get_zone_state(zone_id)
            if zone_state and "temperature_sensor_entity_id" in zone_state:
                entity_id = zone_state["temperature_sensor_entity_id"]
                if isinstance(entity_id, str):
                    sensor_entity_ids.append(entity_id)

        if sensor_entity_ids:
            cancel = async_track_state_change_event(
                self.hass, sensor_entity_ids, self._handle_temperature_change
            )
            self._cancel_listeners.append(cancel)
            _LOGGER.info(
                "Temperature change automation listening to %d zone sensors",
                len(sensor_entity_ids),
            )

        # Set up listener for main climate entity
        config = await self.redis_client.get_config()
        if config:
            main_climate_entity_id = config.get("main_climate_entity_id")
            if main_climate_entity_id:
                cancel = async_track_state_change_event(
                    self.hass, [main_climate_entity_id], self._handle_main_climate_change
                )
                self._cancel_listeners.append(cancel)
                _LOGGER.info(
                    "Temperature change automation listening to main climate entity: %s",
                    main_climate_entity_id,
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

    @callback
    def _handle_main_climate_change(self, event: Event) -> None:
        """
        Handle main climate entity state change.

        Args:
            event: State change event

        Tasks:
            - Update main climate current_temperature in Redis
            - Update hvac_mode and hvac_action in Redis
            - Debounce event (5 seconds)
            - Enqueue calculate_main_temp job
            - Enqueue update_valves job
        """
        # Cancel previous update task if still running
        if self._update_main_climate_task and not self._update_main_climate_task.done():
            self._update_main_climate_task.cancel()

        # Create async task to update Redis
        # Wrap in try-except to catch any task creation errors
        try:
            self._update_main_climate_task = asyncio.create_task(
                self._update_main_climate_state(event)
            )
            # Add done callback to log exceptions
            self._update_main_climate_task.add_done_callback(
                self._handle_update_main_climate_exception
            )
        except Exception as err:
            _LOGGER.error("Failed to create task for main climate state update: %s", err)

        # Debounce job enqueuing
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounced_enqueue())

    def _handle_update_main_climate_exception(self, task: asyncio.Task) -> None:
        """
        Handle exceptions from _update_main_climate_state task.

        Args:
            task: The completed task
        """
        try:
            # This will raise if the task had an exception
            task.result()
        except asyncio.CancelledError:
            # Task cancellation is expected during shutdown
            pass
        except Exception as err:
            _LOGGER.error("Error updating main climate state in Redis: %s", err, exc_info=True)

    async def _update_main_climate_state(self, event: Event) -> None:
        """
        Update main climate state in Redis from state change event.

        Args:
            event: State change event
        """
        new_state = event.data.get("new_state")
        if not new_state:
            return

        # Get current main climate state from Redis
        main_climate_state = await self.redis_client.get_main_climate_state()
        if not main_climate_state:
            _LOGGER.warning("Main climate state not found in Redis")
            return

        # Update current_temperature if available in attributes
        attrs = new_state.attributes
        current_temp = attrs.get("current_temperature")
        if current_temp is not None:
            try:
                main_climate_state["current_temperature"] = float(current_temp)
                _LOGGER.debug(
                    "Updated main climate current_temperature in Redis: %.1f°C",
                    main_climate_state["current_temperature"],
                )
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Invalid current_temperature value from main climate: %s",
                    current_temp,
                )

        # Update hvac_mode from state
        if new_state.state:
            main_climate_state["hvac_mode"] = new_state.state

        # Update hvac_action if available
        hvac_action = attrs.get("hvac_action")
        if hvac_action:
            main_climate_state["hvac_action"] = hvac_action

        # Write updated state to Redis
        await self.redis_client.set_main_climate_state(main_climate_state)

    async def _debounced_enqueue(self) -> None:
        """Debounce wrapper that waits 5 seconds before enqueuing."""
        try:
            await asyncio.sleep(5)
            await self._enqueue_jobs()
        except asyncio.CancelledError:
            # Task was cancelled during debounce wait, this is expected behavior
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

        # Cancel update main climate task if running
        if self._update_main_climate_task and not self._update_main_climate_task.done():
            self._update_main_climate_task.cancel()
            try:
                await self._update_main_climate_task
            except asyncio.CancelledError:
                # Task cancellation is expected during cleanup
                pass

        # Cancel debounce task if running
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                # Task cancellation is expected during cleanup
                pass
