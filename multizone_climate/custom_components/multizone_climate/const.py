"""Constants for the Multizone Climate integration."""

DOMAIN = "multizone_climate"

# Notification constants
NOTIFICATION_ID_RESTART = "multizone_climate_restart_required"
NOTIFICATION_TITLE_RESTART = "Multizone Climate: Restart Required"
NOTIFICATION_MESSAGE_RESTART = (
    "The Multizone Climate integration has been installed. "
    "Please restart Home Assistant for the changes to take full effect."
)

# Job type constants
JOB_TYPE_CALCULATE_MAIN_TEMP = "calculate_main_temp"
JOB_TYPE_UPDATE_VALVES = "update_valves"

# Attribute name constants
ATTR_SATISFACTION = "satisfaction"
ATTR_VALVE_STATE = "valve_state"
ATTR_TEMPERATURE_RISING = "temperature_rising"
ATTR_TEMPERATURE_FALLING = "temperature_falling"
ATTR_PRIORITY = "priority"
ATTR_IS_FALLBACK = "is_fallback_valve"
ATTR_OUTDOOR_TEMPERATURE = "outdoor_temperature"
ATTR_MULTIZONE_ENABLED = "multizone_enabled"

# State/Action constants
STATE_UNKNOWN = "unknown"
HVAC_ACTION_HEATING = "heating"
HVAC_ACTION_COOLING = "cooling"
HVAC_ACTION_OFF = "off"

# Alternative action strings (for compatibility)
HVAC_ACTION_COOL = "cool"
HVAC_ACTION_IDLE = "idle"
