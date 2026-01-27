"""Data coordinator for Multizone Climate integration."""

import asyncio
import logging
from datetime import timedelta
import os
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateCoordinator(DataUpdateCoordinator):
    """Coordinator to poll backend for commands and manage state updates."""

    # Command retry configuration
    MAX_COMMAND_RETRIES = 5
    RETRY_DELAY_SECONDS = 5

    def __init__(self, hass: HomeAssistant, backend_url: str):
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
        if self.session:
            await self.session.close()

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
