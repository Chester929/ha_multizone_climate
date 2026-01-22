#!/bin/bash

# Script to initialize Redis with example zone configuration

set -e

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

echo "Initializing Redis with example zone configuration..."

# Build redis-cli command arguments
REDIS_ARGS=(-h "$REDIS_HOST" -p "$REDIS_PORT")
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_ARGS+=(-a "$REDIS_PASSWORD")
fi

# Set global configuration
echo "Setting global configuration..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:config \
    main_climate_entity_id "climate.main_thermostat" \
    main_target_all_zones_satisfied "0.5" \
    use_average_mode "false" \
    min_valves_open "1" \
    main_min_temp "18.0" \
    main_max_temp "30.0" \
    main_change_threshold "0.5" \
    valve_actuation_delay "120" \
    coordinator_interval "15" \
    satisfaction_eps "0.0"

# Add zones to the list
echo "Adding zones to list..."
redis-cli "${REDIS_ARGS[@]}" DEL multizone:zones
redis-cli "${REDIS_ARGS[@]}" RPUSH multizone:zones "bedroom" "living_room" "kitchen" "bathroom"

# Configure bedroom zone
echo "Configuring bedroom zone..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:zone:bedroom \
    id "bedroom" \
    name "Bedroom" \
    enabled "true" \
    temperature_sensor_entity_id "sensor.bedroom_temperature" \
    valve_switch_entity_id "switch.bedroom_valve" \
    current_temperature "21.5" \
    target_temperature "22.0" \
    satisfaction "underheated" \
    valve_state "open" \
    temperature_rising "true" \
    temperature_falling "false" \
    target_change_threshold "0.1" \
    opening_offset "0.3" \
    closing_offset "0.3" \
    is_fallback_valve "true" \
    priority "10"

# Configure living room zone
echo "Configuring living room zone..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:zone:living_room \
    id "living_room" \
    name "Living Room" \
    enabled "true" \
    temperature_sensor_entity_id "sensor.living_room_temperature" \
    valve_switch_entity_id "switch.living_room_valve" \
    current_temperature "20.8" \
    target_temperature "21.0" \
    satisfaction "satisfied" \
    valve_state "open" \
    temperature_rising "false" \
    temperature_falling "false" \
    target_change_threshold "0.1" \
    opening_offset "0.3" \
    closing_offset "0.3" \
    is_fallback_valve "true" \
    priority "9"

# Configure kitchen zone
echo "Configuring kitchen zone..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:zone:kitchen \
    id "kitchen" \
    name "Kitchen" \
    enabled "true" \
    temperature_sensor_entity_id "sensor.kitchen_temperature" \
    valve_switch_entity_id "switch.kitchen_valve" \
    current_temperature "19.5" \
    target_temperature "20.0" \
    satisfaction "underheated" \
    valve_state "open" \
    temperature_rising "true" \
    temperature_falling "false" \
    target_change_threshold "0.1" \
    opening_offset "0.3" \
    closing_offset "0.3" \
    is_fallback_valve "false" \
    priority "5"

# Configure bathroom zone
echo "Configuring bathroom zone..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:zone:bathroom \
    id "bathroom" \
    name "Bathroom" \
    enabled "false" \
    temperature_sensor_entity_id "sensor.bathroom_temperature" \
    valve_switch_entity_id "switch.bathroom_valve" \
    current_temperature "22.0" \
    target_temperature "23.0" \
    satisfaction "satisfied" \
    valve_state "closed" \
    temperature_rising "false" \
    temperature_falling "false" \
    target_change_threshold "0.1" \
    opening_offset "0.3" \
    closing_offset "0.3" \
    is_fallback_valve "false" \
    priority "8"

# Set main climate state
echo "Setting main climate state..."
redis-cli "${REDIS_ARGS[@]}" HSET multizone:main_climate \
    entity_id "climate.main_thermostat" \
    current_temperature "20.8" \
    target_temperature "21.0" \
    outdoor_temperature "5.0" \
    hvac_mode "MANUAL" \
    hvac_action "HEATING" \
    multizone_enabled "true"

echo "✓ Redis initialized successfully with example configuration"
echo ""
echo "You can now access the frontend at http://localhost:8099"
echo "API is available at http://localhost:8080"
