# Temperature Data Flow Documentation

## Question: How does the backend actualize these values?
- `main_current_temperature`
- `main_target_temperature`
- `outdoor_temperature`

## Architecture Overview

The system has three components:
1. **Home Assistant Integration** (Python) - Frontend integration
2. **Backend Logic Service** (Go) - Core algorithms and state management
3. **Redis** - Shared state storage

## Data Flow for Each Temperature Value

### 1. Main Current Temperature (`main_current_temperature`)

**Source:** Main HVAC thermostat entity in Home Assistant

**Flow:**
```
Main Climate Entity (HA)
    ↓ (reads state)
HA Integration Coordinator
    ↓ (polls /api/integration/state)
Backend API Handler (IntegrationGetStateHandler)
    ↓ (reads from Redis key: multizone:config)
Redis Storage
    ↑ (writes via config updates or external source)
Backend/External Process
```

**Details:**
- The backend stores `main_current_temperature` in Redis under the `multizone:config` hash
- The HA integration's coordinator polls the backend API endpoint `/api/integration/state`
- The backend reads from `config["main_current_temperature"]` and returns it in the response
- This value represents the current temperature reading from the main HVAC thermostat

**Code References:**
- **Backend:** `internal/api/handlers.go:IntegrationGetStateHandler()` (lines 1438-1442)
  ```go
  if currentTemp, ok := config["main_current_temperature"]; ok && currentTemp != "" {
      if floatVal, err := strconv.ParseFloat(currentTemp, 64); err == nil {
          mainClimate["current_temperature"] = floatVal
      }
  }
  ```
- **HA Integration:** `coordinator.py:_fetch_system_state()` fetches from backend API
- **HA Sensor:** `sensor.py:MultizoneTemperatureSensor` displays the value

### 2. Main Target Temperature (`main_target_temperature`)

**Source:** Calculated by backend algorithm based on zone requirements

**Flow:**
```
Zone Temperature Sensors (HA)
    ↓ (state changes)
HA Zone Climate Entities
    ↓ (calls coordinator.push_state_update)
Backend API (POST /api/integration/state_update)
    ↓ (updates zone in Redis)
Redis Zone Data (multizone:zone:*)
    ↓ (triggers calculation job)
Backend Worker (ProcessCalculateTemp)
    ↓ (runs algorithm.CalculateMainTargetTemperature)
Backend Algorithm
    ↓ (stores result in Redis)
Redis Config (multizone:config)
    ↓ (fetched by integration)
Backend API (GET /api/integration/state)
    ↓ (returns to HA)
HA Integration Coordinator
    ↓ (displays)
HA Sensor Entity
```

**Details:**
- Zone climate entities in HA monitor their temperature sensors
- When a zone's temperature changes, it calls `coordinator.push_state_update(zone_id, current_temp)`
- Backend receives this via `/api/integration/state_update` endpoint
- Backend stores the zone temperature in Redis and enqueues a calculation job
- Worker processes the job and runs `algorithm.CalculateMainTargetTemperature()`
- Algorithm considers all zones' targets, priorities, and satisfaction states
- Calculated target is stored in Redis `multizone:config` hash as `main_target_temperature`
- HA integration fetches this value when polling `/api/integration/state`

**Code References:**
- **HA Integration:** `climate.py:_async_update_from_sensor()` (line 371)
  ```python
  sensor_state = self.hass.states.get(self._temp_sensor_entity_id)
  new_temp = float(sensor_state.state)
  await self.coordinator.push_state_update(self._zone_id, new_temp)
  ```
- **Backend API:** `handlers.go:IntegrationStateUpdateHandler()` (line 1165)
- **Backend Worker:** `processor.go:ProcessCalculateTemp()` (line 36)
- **Backend Algorithm:** `algorithm/temperature.go:CalculateMainTargetTemperature()`
- **Backend Storage:** `handlers.go:IntegrationGetStateHandler()` (lines 1444-1448)
  ```go
  if targetTemp, ok := config["main_target_temperature"]; ok && targetTemp != "" {
      if floatVal, err := strconv.ParseFloat(targetTemp, 64); err == nil {
          mainClimate["target_temperature"] = floatVal
      }
  }
  ```

### 3. Outdoor Temperature (`outdoor_temperature`)

**Source:** Currently from backend Redis configuration

**Flow:**
```
External Source / Config Update
    ↓ (writes to Redis)
Redis Config (multizone:config)
    ↓ (read by API handler)
Backend API (GET /api/integration/state)
    ↓ (returns in main_climate object)
HA Integration Coordinator
    ↓ (coordinator.data["main_climate"]["outdoor_temperature"])
HA Sensor Entity (outdoor_temperature)
```

**Details:**
- The outdoor temperature is stored in Redis under `multizone:config` hash
- It can be updated via:
  - Direct Redis updates
  - Backend configuration management
  - Future integration with weather services
  - API updates from external systems
- The HA integration simply displays whatever value the backend provides
- The backend may use this value for heating curve calculations or other algorithms

**Code References:**
- **Backend Storage:** `handlers.go:IntegrationGetStateHandler()` (lines 1450-1454)
  ```go
  if outdoorTemp, ok := config["outdoor_temperature"]; ok && outdoorTemp != "" {
      if floatVal, err := strconv.ParseFloat(outdoorTemp, 64); err == nil {
          mainClimate["outdoor_temperature"] = floatVal
      }
  }
  ```
- **HA Sensor:** `sensor.py:MultizoneTemperatureSensor` with `sensor_type="outdoor_temperature"`
  ```python
  elif self.sensor_type == "outdoor_temperature":
      value = main_climate.get("outdoor_temperature")
  ```

**Note:** The outdoor temperature sensor was previously planned to read from a HA sensor entity, but the correct implementation is to read from backend data, allowing the backend to manage the outdoor temperature source.

## API Endpoints

### GET `/api/integration/state`
**Purpose:** Fetch complete system state for HA integration

**Returns:**
```json
{
  "config": { /* global configuration */ },
  "main_climate": {
    "entity_id": "climate.main",
    "current_temperature": 22.5,
    "target_temperature": 23.0,
    "outdoor_temperature": 5.2,
    "hvac_action": "heating",
    "multizone_enabled": true
  },
  "zones": { /* zone data */ },
  "calculate_queue_size": 0,
  "valve_queue_size": 0
}
```

### POST `/api/integration/state_update`
**Purpose:** Zone entities push temperature updates to backend

**Request:**
```json
{
  "zone_id": "bedroom",
  "current_temperature": 21.5,
  "target_temperature": 22.0
}
```

**Effect:**
- Updates zone state in Redis
- Triggers calculation job to recalculate main target temperature

## Redis Data Structure

### Config Hash: `multizone:config`
```
main_climate_entity_id: "climate.main"
main_current_temperature: "22.5"
main_target_temperature: "23.0"
outdoor_temperature: "5.2"
multizone_enabled: "true"
hvac_action: "heating"
... other config fields ...
```

### Zone Hash: `multizone:zone:{zone_id}`
```
id: "bedroom"
name: "Bedroom"
current_temperature: "21.5"
target_temperature: "22.0"
temperature_sensor_entity_id: "sensor.bedroom_temp"
valve_switch_entity_id: "switch.bedroom_valve"
... other zone fields ...
```

## Update Frequency

1. **Zone Temperature Updates:** Event-driven when sensor state changes in HA
2. **Main Current/Target Temperature:** Polled by coordinator (default: 30 seconds)
3. **Outdoor Temperature:** Depends on backend update mechanism

## Future Enhancements

Potential improvements for outdoor temperature:

1. **Weather Integration:** Backend could fetch from weather API
2. **HA Weather Entity:** Backend could subscribe to HA weather entity updates
3. **External Sensor:** Backend could read from dedicated outdoor sensor
4. **Manual Updates:** Admin API to update outdoor temperature

## Summary

| Temperature | Source | Updated By | Update Frequency |
|------------|--------|------------|------------------|
| `main_current_temperature` | Main HVAC thermostat | Backend config | Coordinator poll (~30s) |
| `main_target_temperature` | Backend algorithm | Zone temp changes | Event-driven + job queue |
| `outdoor_temperature` | Backend config/storage | External/manual | Varies (config-dependent) |

All three values are:
- Stored in Redis `multizone:config` hash
- Fetched by HA integration via `/api/integration/state` API
- Displayed by `MultizoneTemperatureSensor` entities
- Read from `coordinator.data["main_climate"]`

The key architectural principle is **separation of concerns:**
- **Backend** manages business logic, calculations, and state
- **HA Integration** focuses on UI, sensor reading, and command execution
- **Redis** provides the single source of truth for state
