"""Data coordinator for Multizone Climate integration."""
import logging
from datetime import timedelta
import os

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MultizoneClimateCoordinator(DataUpdateCoordinator):
    """Coordinator to poll backend for commands and manage state updates."""

    def __init__(self, hass: HomeAssistant, backend_url: str):
        """Initialize the coordinator."""
        # Get coordinator interval from environment variable (set by addon)
        interval_seconds = int(os.environ.get("COORDINATOR_INTERVAL", "30"))
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.backend_url = backend_url.rstrip("/")
        self._session = None

    async def _async_update_data(self):
        """Fetch commands from backend and execute them."""
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            # Get pending commands from backend
            async with self._session.get(
                f"{self.backend_url}/api/integration/commands",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Backend returned status {response.status}")
                
                commands = await response.json()
                
                if not commands:
                    return {}

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
                        _LOGGER.error(f"Failed to execute command on {entity_id}: {err}")

                # Acknowledge executed commands
                if executed_entities:
                    await self._acknowledge_commands(executed_entities)

                return {"commands_executed": len(executed_entities)}

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with backend: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")

    async def _execute_command(self, entity_id: str, action: str, value):
        """Execute a command on a Home Assistant entity."""
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

    async def _acknowledge_commands(self, entity_ids: list[str]):
        """Acknowledge executed commands to backend."""
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            async with self._session.delete(
                f"{self.backend_url}/api/integration/commands",
                json={"entity_ids": entity_ids},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(f"Failed to acknowledge commands: status {response.status}")
                else:
                    _LOGGER.debug(f"Acknowledged {len(entity_ids)} commands")
        except Exception as err:
            _LOGGER.error(f"Error acknowledging commands: {err}")

    async def push_state_update(self, zone_id: str, current_temp: float):
        """Push temperature state update to backend."""
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            async with self._session.post(
                f"{self.backend_url}/api/integration/state_update",
                json={"zone_id": zone_id, "current_temp": current_temp},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    _LOGGER.warning(
                        f"Failed to push state update for zone {zone_id}: status {response.status}"
                    )
                else:
                    _LOGGER.debug(f"Pushed state update for zone {zone_id}: {current_temp}°C")
        except Exception as err:
            _LOGGER.error(f"Error pushing state update for zone {zone_id}: {err}")

    async def async_shutdown(self):
        """Cleanup on shutdown."""
        if self._session:
            await self._session.close()
