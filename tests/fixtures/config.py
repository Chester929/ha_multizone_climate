# Sample configuration data for testing
SAMPLE_CONFIG = {
    "main_climate_entity_id": "climate.main_thermostat",
    "use_average_mode": False,
    "main_target_all_zones_satisfied": 0.5,
    "min_valves_open": 1,
    "main_min_temp": 18.0,
    "main_max_temp": 30.0,
    "main_change_threshold": 0.5,
}

SAMPLE_ZONE = {
    "id": "bedroom",
    "name": "Bedroom",
    "temperature_sensor_entity_id": "sensor.bedroom_temperature",
    "valve_switch_entity_id": "switch.bedroom_valve",
    "target_temperature": 21.0,
    "opening_offset": 0.3,
    "closing_offset": 0.3,
}
