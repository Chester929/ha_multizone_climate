"""Constants for the Multizone Climate integration."""

DOMAIN = "multizone_climate"

# Configuration constants
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
CONF_COORDINATOR_INTERVAL = "coordinator_interval"
CONF_SATISFACTION_EPS = "satisfaction_eps"

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
DEFAULT_COORDINATOR_INTERVAL = 15
DEFAULT_SATISFACTION_EPS = 0.0

# Zone configuration
CONF_ZONE_NAME = "zone_name"
CONF_ZONE_TEMP_SENSOR = "temperature_sensor_entity_id"
CONF_ZONE_VALVE_SWITCH = "valve_switch_entity_id"
CONF_ZONE_TARGET_THRESHOLD = "target_change_threshold"
CONF_ZONE_OPENING_OFFSET = "opening_offset"
CONF_ZONE_CLOSING_OFFSET = "closing_offset"
CONF_ZONE_IS_FALLBACK = "is_fallback_valve"
CONF_ZONE_PRIORITY = "priority"

# Zone defaults
DEFAULT_ZONE_TARGET_THRESHOLD = 0.1
DEFAULT_ZONE_OPENING_OFFSET = 0.3
DEFAULT_ZONE_CLOSING_OFFSET = 0.3
DEFAULT_ZONE_IS_FALLBACK = False
DEFAULT_ZONE_PRIORITY = 0

# Entity attributes
ATTR_MULTIZONE_ENABLED = "multizone_enabled"
ATTR_ZONES = "zones"
ATTR_SATISFACTION = "satisfaction"
ATTR_TEMPERATURE_DIRECTION = "temperature_direction"
ATTR_VALVE_STATE = "valve_state"

# States
STATE_UNDERHEATED = "underheated"
STATE_SATISFIED = "satisfied"
STATE_OVERHEATED = "overheated"
STATE_UNDERCOOLED = "undercooled"
STATE_OVERCOOLED = "overcooled"

# Services
SERVICE_ADD_ZONE = "add_zone"
SERVICE_REMOVE_ZONE = "remove_zone"
SERVICE_UPDATE_ZONE = "update_zone"
SERVICE_ENABLE_MULTIZONE = "enable_multizone"
SERVICE_DISABLE_MULTIZONE = "disable_multizone"
