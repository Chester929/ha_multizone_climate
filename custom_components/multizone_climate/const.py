"""Constants for the Multizone Climate integration."""

# Integration domain and version
DOMAIN = "multizone_climate"
VERSION = "0.1.0"  # Should match version in manifest.json

# Configuration and options
CONF_REDIS_HOST = "redis_host"
CONF_REDIS_PORT = "redis_port"
CONF_REDIS_PASSWORD = "redis_password"
CONF_REDIS_DB = "redis_db"
CONF_REDIS_KEY_PREFIX = "redis_key_prefix"
CONF_MAIN_CLIMATE_ENTITY = "main_climate_entity_id"
CONF_MAIN_TARGET_ALL_ZONES_SATISFIED = "main_target_all_zones_satisfied"
CONF_USE_AVERAGE_MODE = "use_average_mode"
CONF_MIN_VALVES_OPEN = "min_valves_open"
CONF_MAIN_MIN_TEMP = "main_min_temp"
CONF_MAIN_MAX_TEMP = "main_max_temp"
CONF_MAIN_CHANGE_THRESHOLD = "main_change_threshold"
CONF_VALVE_ACTUATION_DELAY = "valve_actuation_delay"
CONF_COMMAND_COOLDOWN = "command_cooldown"
CONF_COORDINATOR_INTERVAL = "coordinator_interval"
CONF_JOB_STATUS_TTL = "job_status_ttl"
CONF_SATISFACTION_EPS = "satisfaction_eps"

# Zone configuration
CONF_ZONE_NAME = "zone_name"
CONF_ZONE_TEMP_SENSOR = "zone_temperature_sensor"
CONF_ZONE_VALVE_SWITCH = "zone_valve_switch"
CONF_ZONE_TARGET_THRESHOLD = "zone_target_change_threshold"
CONF_ZONE_OPENING_OFFSET = "zone_opening_offset"
CONF_ZONE_CLOSING_OFFSET = "zone_closing_offset"
CONF_ZONE_IS_FALLBACK = "zone_is_fallback_valve"
CONF_ZONE_PRIORITY = "zone_priority"

# Default values
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_REDIS_KEY_PREFIX = "ha_multizone"
DEFAULT_MAIN_TARGET_ALL_ZONES_SATISFIED = 0.5
DEFAULT_USE_AVERAGE_MODE = False
DEFAULT_MIN_VALVES_OPEN = 1
DEFAULT_MAIN_MIN_TEMP = 18.0
DEFAULT_MAIN_MAX_TEMP = 30.0
DEFAULT_MAIN_CHANGE_THRESHOLD = 0.5
DEFAULT_VALVE_ACTUATION_DELAY = 120
DEFAULT_COMMAND_COOLDOWN = 60
DEFAULT_COORDINATOR_INTERVAL = 15
DEFAULT_JOB_STATUS_TTL = 900
DEFAULT_SATISFACTION_EPS = 0.0
DEFAULT_ZONE_TARGET_THRESHOLD = 0.1
DEFAULT_ZONE_OPENING_OFFSET = 0.3
DEFAULT_ZONE_CLOSING_OFFSET = 0.3
DEFAULT_ZONE_IS_FALLBACK = False
DEFAULT_ZONE_PRIORITY = 0

# Satisfaction states
STATE_UNDERHEATED = "underheated"
STATE_SATISFIED = "satisfied"
STATE_OVERHEATED = "overheated"
STATE_UNDERCOOLED = "undercooled"
STATE_OVERCOOLED = "overcooled"
STATE_UNKNOWN = "unknown"

# HVAC actions
HVAC_ACTION_HEATING = "heating"
HVAC_ACTION_COOLING = "cooling"
HVAC_ACTION_IDLE = "idle"
HVAC_ACTION_OFF = "off"

# Job types
JOB_TYPE_CALCULATE_MAIN_TEMP = "calculate_main_temp"
JOB_TYPE_UPDATE_VALVES = "update_valves"
JOB_TYPE_SAFETY_CHECK = "safety_check"

# Redis key patterns
REDIS_KEY_CONFIG = "config"
REDIS_KEY_ZONES = "zones"
REDIS_KEY_MAIN_CLIMATE = "main_climate"
REDIS_KEY_ZONE = "zone:{zone_id}"
REDIS_KEY_QUEUE_CALC = "queue:calculate_main_temp"
REDIS_KEY_QUEUE_VALVE = "queue:update_valves"
REDIS_KEY_VALVE_LOCK = "valvelock:{valve_id}"
REDIS_KEY_JOB_LOCK = "joblock:{job_type}"
REDIS_KEY_JOB_STATUS = "jobstatus:{job_id}"

# Attributes
ATTR_SATISFACTION = "satisfaction"
ATTR_VALVE_STATE = "valve_state"
ATTR_TEMPERATURE_RISING = "temperature_rising"
ATTR_TEMPERATURE_FALLING = "temperature_falling"
ATTR_PRIORITY = "priority"
ATTR_IS_FALLBACK = "is_fallback_valve"
ATTR_OUTDOOR_TEMPERATURE = "outdoor_temperature"
ATTR_MULTIZONE_ENABLED = "multizone_enabled"

# Services
SERVICE_RECALCULATE = "recalculate"
SERVICE_FORCE_VALVE_UPDATE = "force_valve_update"
