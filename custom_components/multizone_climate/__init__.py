"""
Home Assistant Multizone Climate Integration.

This integration manages multi-zone climate control with coordinated valve management
and main thermostat control.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_REDIS_HOST,
    CONF_REDIS_PORT,
    CONF_REDIS_PASSWORD,
    CONF_REDIS_DB,
    CONF_REDIS_KEY_PREFIX,
    CONF_COORDINATOR_INTERVAL,
    CONF_JOB_STATUS_TTL,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_KEY_PREFIX,
    DEFAULT_COORDINATOR_INTERVAL,
    DEFAULT_JOB_STATUS_TTL,
    SERVICE_RECALCULATE,
    SERVICE_FORCE_VALVE_UPDATE,
    JOB_TYPE_CALCULATE_MAIN_TEMP,
    JOB_TYPE_UPDATE_VALVES,
)
from .core import RedisClient, ValveController, SafetyChecker
from .coordinator import MultizoneClimateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms that this integration provides
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the Multizone Climate component from configuration.yaml.
    
    Args:
        hass: Home Assistant instance
        config: Configuration dict from configuration.yaml
    
    Returns:
        bool: True if setup successful
    """
    # Integration uses config flow, no configuration.yaml setup needed
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Multizone Climate from a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry containing integration configuration
    
    Returns:
        bool: True if setup successful
    """
    hass.data.setdefault(DOMAIN, {})
    
    # Extract Redis configuration from config entry
    redis_host = entry.data.get(CONF_REDIS_HOST, DEFAULT_REDIS_HOST)
    redis_port = entry.data.get(CONF_REDIS_PORT, DEFAULT_REDIS_PORT)
    redis_password = entry.data.get(CONF_REDIS_PASSWORD)
    redis_db = entry.data.get(CONF_REDIS_DB, DEFAULT_REDIS_DB)
    redis_key_prefix = entry.data.get(CONF_REDIS_KEY_PREFIX, DEFAULT_REDIS_KEY_PREFIX)
    coordinator_interval = entry.data.get(CONF_COORDINATOR_INTERVAL, DEFAULT_COORDINATOR_INTERVAL)
    job_status_ttl = entry.data.get(CONF_JOB_STATUS_TTL, DEFAULT_JOB_STATUS_TTL)
    
    try:
        # Initialize Redis client
        redis_client = RedisClient(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            key_prefix=redis_key_prefix,
            job_status_ttl=job_status_ttl,
        )
        
        # Connect to Redis
        await redis_client.connect()
        _LOGGER.info("Redis client connected for entry %s", entry.entry_id)
        
        # Get config from Redis (or initialize with defaults from entry.data)
        config = await redis_client.get_config()
        if not config:
            # Initialize with defaults from entry data
            from .const import (
                CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                CONF_USE_AVERAGE_MODE,
                CONF_MIN_VALVES_OPEN,
                CONF_MAIN_MIN_TEMP,
                CONF_MAIN_MAX_TEMP,
                CONF_MAIN_CHANGE_THRESHOLD,
                CONF_VALVE_ACTUATION_DELAY,
                CONF_COMMAND_COOLDOWN,
                CONF_SATISFACTION_EPS,
                DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED,
                DEFAULT_USE_AVERAGE_MODE,
                DEFAULT_MIN_VALVES_OPEN,
                DEFAULT_MAIN_MIN_TEMP,
                DEFAULT_MAIN_MAX_TEMP,
                DEFAULT_MAIN_CHANGE_THRESHOLD,
                DEFAULT_VALVE_ACTUATION_DELAY,
                DEFAULT_COMMAND_COOLDOWN,
                DEFAULT_SATISFACTION_EPS,
            )
            config = {
                CONF_MAIN_TARGET_ALL_ZONES_SATISFIED: entry.data.get(
                    CONF_MAIN_TARGET_ALL_ZONES_SATISFIED,
                    DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED
                ),
                CONF_USE_AVERAGE_MODE: entry.data.get(
                    CONF_USE_AVERAGE_MODE,
                    DEFAULT_USE_AVERAGE_MODE
                ),
                CONF_MIN_VALVES_OPEN: entry.data.get(
                    CONF_MIN_VALVES_OPEN,
                    DEFAULT_MIN_VALVES_OPEN
                ),
                CONF_MAIN_MIN_TEMP: entry.data.get(
                    CONF_MAIN_MIN_TEMP,
                    DEFAULT_MAIN_MIN_TEMP
                ),
                CONF_MAIN_MAX_TEMP: entry.data.get(
                    CONF_MAIN_MAX_TEMP,
                    DEFAULT_MAIN_MAX_TEMP
                ),
                CONF_MAIN_CHANGE_THRESHOLD: entry.data.get(
                    CONF_MAIN_CHANGE_THRESHOLD,
                    DEFAULT_MAIN_CHANGE_THRESHOLD
                ),
                CONF_VALVE_ACTUATION_DELAY: entry.data.get(
                    CONF_VALVE_ACTUATION_DELAY,
                    DEFAULT_VALVE_ACTUATION_DELAY
                ),
                CONF_COMMAND_COOLDOWN: entry.data.get(
                    CONF_COMMAND_COOLDOWN,
                    DEFAULT_COMMAND_COOLDOWN
                ),
                CONF_SATISFACTION_EPS: entry.data.get(
                    CONF_SATISFACTION_EPS,
                    DEFAULT_SATISFACTION_EPS
                ),
            }
            await redis_client.set_config(config)
        
        # Initialize core components
        valve_controller = ValveController(redis_client, config)
        safety_checker = SafetyChecker(redis_client, config)
        
        # Create coordinator
        coordinator = MultizoneClimateCoordinator(
            hass=hass,
            redis_client=redis_client,
            interval=coordinator_interval,
        )
        
        # Store components in hass.data
        hass.data[DOMAIN][entry.entry_id] = {
            "redis_client": redis_client,
            "coordinator": coordinator,
            "valve_controller": valve_controller,
            "safety_checker": safety_checker,
        }
        
        # Create main device entry
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name="Multizone Climate",
            manufacturer="Multizone Climate",
            model="Main Controller",
        )
        
        # Forward setup to platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Register services
        async def handle_recalculate(call: ServiceCall) -> None:
            """Handle recalculate service call."""
            _LOGGER.debug("Recalculate service called")
            await redis_client.enqueue_job(
                JOB_TYPE_CALCULATE_MAIN_TEMP,
                {
                    "job_id": f"recalc_{entry.entry_id}_{int(hass.loop.time())}",
                    "trigger": "service_call",
                    "enqueued_at": hass.loop.time(),
                }
            )
        
        async def handle_force_valve_update(call: ServiceCall) -> None:
            """Handle force valve update service call."""
            _LOGGER.debug("Force valve update service called")
            await redis_client.enqueue_job(
                JOB_TYPE_UPDATE_VALVES,
                {
                    "job_id": f"valve_update_{entry.entry_id}_{int(hass.loop.time())}",
                    "trigger": "service_call",
                    "enqueued_at": hass.loop.time(),
                }
            )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_RECALCULATE,
            handle_recalculate,
        )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_FORCE_VALVE_UPDATE,
            handle_force_valve_update,
        )
        
        _LOGGER.info("Multizone Climate integration setup complete for entry %s", entry.entry_id)
        
        return True
        
    except Exception as err:
        _LOGGER.error("Failed to set up Multizone Climate: %s", err)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry to unload
    
    Returns:
        bool: True if unload successful
    """
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Get stored components
        data = hass.data[DOMAIN].pop(entry.entry_id)
        
        # Close Redis connection
        redis_client = data["redis_client"]
        await redis_client.disconnect()
        
        # Unregister services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RECALCULATE)
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_VALVE_UPDATE)
        
        _LOGGER.info("Multizone Climate integration unloaded for entry %s", entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload config entry.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry to reload
    """
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
