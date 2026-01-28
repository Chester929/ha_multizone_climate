"""Data coordinator for Multizone Climate integration."""

import asyncio
import logging
from datetime import timedelta
import os
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, JOB_TYPE_CALCULATE_MAIN_TEMP, JOB_TYPE_UPDATE_VALVES

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateCoordinator(DataUpdateCoordinator):
    """Coordinator to poll backend for commands and manage state updates."""

    # Command retry configuration
    MAX_COMMAND_RETRIES = 5
    RETRY_DELAY_SECONDS = 5
    # Job worker configuration
    JOB_WORKER_INTERVAL = 10  # seconds between job queue checks

    def __init__(self, hass: HomeAssistant, backend_url: str, redis_client: Any = None):
        """Initialize the coordinator."""
        # Get coordinator interval from environment variable (set by addon)
        raw_interval = os.environ.get("COORDINATOR_INTERVAL", "30")
        try:
            interval_seconds = int(raw_interval)
        except ValueError:
            _LOGGER.warning(
                f"Invalid COORDINATOR_INTERVAL value '{raw_interval}'; falling back to default 30 seconds"
            )
            interval_seconds = 30
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.backend_url = backend_url.rstrip("/")
        # Create session with default timeout
        timeout = aiohttp.ClientTimeout(total=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        # Store redis_client for job worker
        self.redis_client = redis_client
        # Job worker task
        self._job_worker_task: asyncio.Task | None = None
        # Job instances (will be initialized later)
        self._update_valves_job: Any = None
        self._calculate_main_temp_job: Any = None

    async def _async_update_data(self) -> dict:
        """Fetch commands from backend and execute them."""
        try:
            # Fetch system state first
            state_data = await self._fetch_system_state()

            # Get pending commands from backend
            async with self.session.get(
                f"{self.backend_url}/api/integration/commands",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Backend returned status {response.status}")

                response_data = await response.json()
                commands = response_data.get("commands", [])

                if commands:
                    _LOGGER.info(f"Received {len(commands)} commands from backend")

                    # Execute commands
                    executed_entities = []
                    for command in commands:
                        entity_id = command.get("entity_id")
                        action = command.get("action")
                        value = command.get("value")

                        if not entity_id or not action:
                            _LOGGER.warning(f"Invalid command: {command}")
                            continue

                        try:
                            await self._execute_command(entity_id, action, value)
                            executed_entities.append(entity_id)
                            _LOGGER.info(f"Executed {action} on {entity_id}")
                        except Exception as err:
                            _LOGGER.error(
                                f"Failed to execute command on {entity_id}: {err}"
                            )

                    # Acknowledge executed commands
                    if executed_entities:
                        await self._acknowledge_commands(executed_entities)

                    state_data["commands_executed"] = len(executed_entities)

                return state_data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with backend: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")

    async def _fetch_system_state(self) -> dict:
        """Fetch current system state from backend."""
        try:
            async with self.session.get(
                f"{self.backend_url}/api/integration/state",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(
                        f"Failed to fetch system state: status {response.status}"
                    )
                    return {}

                state_data = await response.json()
                return state_data

        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error fetching system state: {err}")
            return {}
        except Exception as err:
            _LOGGER.error(f"Unexpected error fetching system state: {err}")
            return {}

    async def _execute_command(self, entity_id: str, action: str, value: Any) -> None:
        """Execute a command on a Home Assistant entity."""
        if not isinstance(entity_id, str) or "." not in entity_id:
            _LOGGER.warning(f"Invalid entity_id format for command: {entity_id}")
            return
        domain = entity_id.split(".")[0]

        if action == "set_temperature" and domain == "climate":
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": value},
                blocking=True,
            )
        elif action == "turn_on" and domain in ["switch", "valve"]:
            await self.hass.services.async_call(
                domain,
                "turn_on",
                {"entity_id": entity_id},
                blocking=True,
            )
        elif action == "turn_off" and domain in ["switch", "valve"]:
            await self.hass.services.async_call(
                domain,
                "turn_off",
                {"entity_id": entity_id},
                blocking=True,
            )
        else:
            _LOGGER.warning(f"Unknown action {action} for entity {entity_id}")

    async def _acknowledge_commands(self, entity_ids: list[str]) -> None:
        """Acknowledge executed commands to backend with retry mechanism."""
        for attempt in range(1, self.MAX_COMMAND_RETRIES + 1):
            try:
                async with self.session.delete(
                    f"{self.backend_url}/api/integration/commands",
                    json={"entity_ids": entity_ids},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            f"Failed to acknowledge commands (attempt {attempt}/{self.MAX_COMMAND_RETRIES}): status {response.status}"
                        )
                        if attempt < self.MAX_COMMAND_RETRIES:
                            await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                            continue
                    else:
                        _LOGGER.debug(f"Acknowledged {len(entity_ids)} commands")
                        return
            except Exception as err:
                _LOGGER.error(
                    f"Error acknowledging commands (attempt {attempt}/{self.MAX_COMMAND_RETRIES}): {err}"
                )
                if attempt < self.MAX_COMMAND_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                    continue

        # After max retries, log error and give up
        _LOGGER.error(
            f"Failed to acknowledge commands after {self.MAX_COMMAND_RETRIES} attempts. Commands: {entity_ids}"
        )

    async def push_state_update(self, zone_id: str, current_temp: float) -> None:
        """Push temperature state update to backend with retry mechanism."""
        for attempt in range(1, self.MAX_COMMAND_RETRIES + 1):
            try:
                async with self.session.post(
                    f"{self.backend_url}/api/integration/state_update",
                    json={"zone_id": zone_id, "current_temperature": current_temp},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            f"Failed to push state update for zone {zone_id} (attempt {attempt}/{self.MAX_COMMAND_RETRIES}): status {response.status}"
                        )
                        if attempt < self.MAX_COMMAND_RETRIES:
                            await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                            continue
                    else:
                        _LOGGER.debug(
                            f"Pushed state update for zone {zone_id}: {current_temp}°C"
                        )
                        return
            except Exception as err:
                _LOGGER.error(
                    f"Error pushing state update for zone {zone_id} (attempt {attempt}/{self.MAX_COMMAND_RETRIES}): {err}"
                )
                if attempt < self.MAX_COMMAND_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                    continue

        # After max retries, log error and give up
        _LOGGER.error(
            f"Failed to push state update for zone {zone_id} after {self.MAX_COMMAND_RETRIES} attempts"
        )

    async def async_shutdown(self) -> None:
        """Cleanup on shutdown."""
        # Stop job worker
        await self.stop_job_worker()
        # Close session
        if self.session:
            await self.session.close()

    async def start_job_worker(self) -> None:
        """
        Start the background job worker.
        
        The job worker processes jobs from Redis queues when multizone is enabled.
        It runs continuously in the background, checking for new jobs every JOB_WORKER_INTERVAL seconds.
        """
        if self._job_worker_task is not None:
            _LOGGER.warning("Job worker already running")
            return
        
        if not self.redis_client:
            _LOGGER.error("Cannot start job worker: redis_client not available")
            return
        
        # Initialize job instances
        from .jobs import UpdateValvesJob, CalculateMainTempJob
        self._update_valves_job = UpdateValvesJob(self.redis_client, self.hass)
        self._calculate_main_temp_job = CalculateMainTempJob(self.redis_client, self.hass)
        
        # Start worker task
        self._job_worker_task = asyncio.create_task(self._job_worker_loop())
        _LOGGER.info("Job worker started")

    async def stop_job_worker(self) -> None:
        """Stop the background job worker."""
        if self._job_worker_task:
            self._job_worker_task.cancel()
            try:
                await self._job_worker_task
            except asyncio.CancelledError:
                pass
            self._job_worker_task = None
            _LOGGER.info("Job worker stopped")

    async def _job_worker_loop(self) -> None:
        """
        Main job worker loop.
        
        Continuously processes jobs from Redis queues when multizone is enabled.
        Checks both calculate_main_temp and update_valves queues.
        """
        _LOGGER.info("Job worker loop starting")
        
        while True:
            try:
                # Check if multizone is enabled
                config = await self.redis_client.get_config()
                multizone_enabled = config.get("multizone_enabled", False) if config else False
                
                if not multizone_enabled:
                    _LOGGER.debug("Job worker: multizone disabled, skipping job processing")
                    await asyncio.sleep(self.JOB_WORKER_INTERVAL)
                    continue
                
                # Process calculate_main_temp jobs
                await self._process_job_queue(
                    JOB_TYPE_CALCULATE_MAIN_TEMP,
                    self._calculate_main_temp_job
                )
                
                # Process update_valves jobs
                await self._process_job_queue(
                    JOB_TYPE_UPDATE_VALVES,
                    self._update_valves_job
                )
                
                # Wait before next iteration
                await asyncio.sleep(self.JOB_WORKER_INTERVAL)
                
            except asyncio.CancelledError:
                _LOGGER.info("Job worker loop cancelled")
                raise
            except Exception as err:
                _LOGGER.error(f"Error in job worker loop: {err}", exc_info=True)
                await asyncio.sleep(self.JOB_WORKER_INTERVAL)

    async def _process_job_queue(self, job_type: str, job_instance: Any) -> None:
        """
        Process all jobs in a specific queue.
        
        Args:
            job_type: Type of job (calculate_main_temp or update_valves)
            job_instance: Job instance to execute
        """
        if not job_instance:
            _LOGGER.error(f"Job instance for {job_type} not initialized")
            return
        
        # Process all jobs in the queue
        jobs_processed = 0
        while True:
            # Dequeue next job
            job_data = await self.redis_client.dequeue_job(job_type)
            if not job_data:
                # Queue is empty
                if jobs_processed > 0:
                    _LOGGER.debug(f"Processed {jobs_processed} {job_type} job(s)")
                break
            
            # Execute the job
            _LOGGER.debug(f"Job {job_type} started: {job_data}")
            
            try:
                result = await job_instance.execute(job_data)
                
                if result.get("status") == "completed":
                    _LOGGER.info(f"Job {job_type} finished successfully: {result.get('result', {})}")
                elif result.get("status") == "skipped":
                    _LOGGER.debug(f"Job {job_type} skipped: {result.get('reason', 'unknown')}")
                elif result.get("status") == "failed":
                    _LOGGER.error(f"Job {job_type} failed: {result.get('error', 'unknown')}")
                else:
                    _LOGGER.warning(f"Job {job_type} returned unknown status: {result.get('status')}")
                    
                jobs_processed += 1
                
            except Exception as err:
                _LOGGER.error(f"Exception executing job {job_type}: {err}", exc_info=True)
                jobs_processed += 1

    def get_config(self) -> dict | None:
        """Get configuration from coordinator data."""
        if self.data:
            value = self.data.get("config")
            # Return the value only if it's a dict, else None
            return value if isinstance(value, dict) else None
        return None

    def get_main_climate_data(self) -> dict | None:
        """Get main climate data from coordinator data."""
        if self.data:
            value = self.data.get("main_climate")
            # Return the value only if it's a dict, else None
            return value if isinstance(value, dict) else None
        return None

    def get_zone_data(self, zone_id: str) -> dict | None:
        """Get zone data from coordinator data."""
        if self.data:
            zones = self.data.get("zones", {})
            if isinstance(zones, dict):
                return zones.get(zone_id)
        return None
