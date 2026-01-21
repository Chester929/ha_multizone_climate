"""Climate platform for Multizone Climate integration."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .coordinator import MultizoneClimateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Multizone Climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    config_data = config_entry.data

    # Extract zone configuration
    zone_name = config_data.get("zone_name", "Zone")
    zone_id = config_entry.entry_id  # Use config entry ID as zone ID
    temperature_sensor = config_data.get("temperature_sensor")
    valve_switch = config_data.get("valve_switch")
    target_temp = config_data.get("target_temperature", 20.0)
    opening_offset = config_data.get("opening_offset", 0.5)
    closing_offset = config_data.get("closing_offset", 0.5)
    priority = config_data.get("priority", 50)
    is_fallback = config_data.get("is_fallback_valve", False)

    # Create the zone climate entity
    entity = MultizoneClimateEntity(
        coordinator=coordinator,
        zone_id=zone_id,
        zone_name=zone_name,
        temperature_sensor=temperature_sensor,
        valve_switch=valve_switch,
        target_temp=target_temp,
        opening_offset=opening_offset,
        closing_offset=closing_offset,
        priority=priority,
        is_fallback=is_fallback,
    )

    async_add_entities([entity])


class MultizoneClimateEntity(ClimateEntity):
    """Representation of a Multizone Climate zone entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(
        self,
        coordinator: MultizoneClimateCoordinator,
        zone_id: str,
        zone_name: str,
        temperature_sensor: str,
        valve_switch: str,
        target_temp: float,
        opening_offset: float,
        closing_offset: float,
        priority: int,
        is_fallback: bool,
    ):
        """Initialize the climate entity."""
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._zone_name = zone_name
        self._temperature_sensor = temperature_sensor
        self._valve_switch = valve_switch
        self._attr_target_temperature = target_temp
        self._opening_offset = opening_offset
        self._closing_offset = closing_offset
        self._priority = priority
        self._is_fallback = is_fallback
        self._attr_current_temperature = None
        self._attr_hvac_mode = HVACMode.HEAT
        self._unsubscribe_sensor = None

        # Set unique ID and device info
        self._attr_unique_id = f"multizone_climate_{zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=f"Multizone Climate - {zone_name}",
            manufacturer="Multizone Climate",
            model="Zone Controller",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Subscribe to temperature sensor state changes
        @callback
        def temperature_sensor_state_listener(event):
            """Handle temperature sensor state changes."""
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in ("unknown", "unavailable"):
                return

            try:
                temperature = float(new_state.state)
                self._attr_current_temperature = temperature
                self.async_write_ha_state()

                # Push state update to backend
                self.hass.async_create_task(
                    self.coordinator.push_state_update(self._zone_id, temperature)
                )
            except (ValueError, TypeError):
                _LOGGER.warning(
                    f"Invalid temperature value from {self._temperature_sensor}: {new_state.state}"
                )

        self._unsubscribe_sensor = async_track_state_change_event(
            self.hass, [self._temperature_sensor], temperature_sensor_state_listener
        )

        # Initialize current temperature from sensor
        sensor_state = self.hass.states.get(self._temperature_sensor)
        if sensor_state and sensor_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_current_temperature = float(sensor_state.state)
            except (ValueError, TypeError):
                pass

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        if self._unsubscribe_sensor:
            self._unsubscribe_sensor()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._zone_name

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._attr_target_temperature = temperature
        self.async_write_ha_state()

        # TODO: Push target temperature update to backend
        # This would require a new backend API endpoint
        _LOGGER.info(
            f"Zone {self._zone_name} target temperature set to {temperature}°C"
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

        _LOGGER.info(f"Zone {self._zone_name} HVAC mode set to {hvac_mode}")

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        return {
            "zone_id": self._zone_id,
            "temperature_sensor": self._temperature_sensor,
            "valve_switch": self._valve_switch,
            "opening_offset": self._opening_offset,
            "closing_offset": self._closing_offset,
            "priority": self._priority,
            "is_fallback_valve": self._is_fallback,
        }
