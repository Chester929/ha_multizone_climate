# Climate Entity Integration Guide

## Overview

This document describes the climate entity integration improvements that enable seamless synchronization between Home Assistant climate entities and multi-zone climate zones.

## Problem Statement

Previously, the multi-zone climate system had three issues:

1. **UI not displaying zone data**: When creating a zone with temperature sensor and valve switch, current temperature and satisfaction were not shown in the UI
2. **No climate entity sync**: Target temperature changes in Home Assistant did not sync to the app, and vice versa
3. **Complex configuration**: Users had to manually specify temperature sensor, valve switch, and target temperature separately

## Solution

### Simplified Configuration

The climate entity is now the **primary configuration source** for a zone. When you configure a zone with a climate entity:

1. **Current temperature** is automatically loaded from the climate entity's `current_temperature` attribute
2. **Target temperature** is automatically loaded from the climate entity's `temperature` attribute
3. **Bi-directional sync** keeps the zone and climate entity in sync

### Configuration Priority

- **Climate Entity**: Primary source for current and target temperature
- **Temperature Sensor**: Optional override for current temperature only
- **Valve Switch**: Required for valve control (separate entity)

## API Changes

### Zone Creation Endpoint: `POST /api/zones`

#### Request Body

```json
{
  "name": "Living Room",
  "climate_entity_id": "climate.living_room",
  "valve_switch_entity_id": "switch.living_room_valve",
  "temperature_sensor_entity_id": "sensor.living_room_temp"  // Optional override
}
```

#### Behavior

1. If `climate_entity_id` is provided and HA integration is enabled:
   - System fetches the climate entity state from Home Assistant
   - Auto-loads `current_temperature` from climate entity (unless `temperature_sensor_entity_id` is provided)
   - Auto-loads `target_temperature` from climate entity (unless explicitly provided in request)
   
2. If `temperature_sensor_entity_id` is provided:
   - System fetches sensor state and uses it for `current_temperature` (overrides climate entity)
   
3. If `valve_switch_entity_id` is provided:
   - System fetches switch state for initial `valve_state`

### Zone List Endpoint: `GET /api/zones`

#### Response

Now returns **all zone fields** instead of just ID and name:

```json
[
  {
    "id": "zone-living-room",
    "name": "Living Room",
    "enabled": "true",
    "current_temperature": "21.5",
    "target_temperature": "22.0",
    "satisfaction": "underheated",
    "valve_state": "open",
    "priority": "50",
    "temperature_sensor_entity_id": "sensor.living_room_temp",
    "valve_switch_entity_id": "switch.living_room_valve",
    "climate_entity_id": "climate.living_room"
  }
]
```

## Integration Behavior

### Home Assistant → App Sync

When a state change occurs in Home Assistant:

1. **Climate Entity Target Temperature Change**:
   - WebSocket event received
   - System updates zone's `target_temperature` in Redis
   - Only updates if temperature changed by more than threshold (0.1°C) to prevent loops
   - Triggers recalculation job

2. **Climate Entity Current Temperature Change** (when no temperature sensor):
   - WebSocket event received
   - System updates zone's `current_temperature` in Redis
   - Triggers recalculation job

3. **Temperature Sensor Change** (when configured):
   - WebSocket event received
   - System updates zone's `current_temperature` in Redis (overrides climate entity)
   - Triggers recalculation job

4. **Valve Switch Change**:
   - WebSocket event received
   - System updates zone's `valve_state` in Redis

### App → Home Assistant Sync

When a zone is updated via the API:

1. **Zone Target Temperature Change**:
   - System updates Redis
   - If zone has `climate_entity_id`, calls HA API to set climate entity temperature
   - Uses `climate.set_temperature` service

2. **Entity Cache Refresh**:
   - When entity IDs are updated, system refreshes the entity cache
   - Ensures WebSocket events are routed correctly

## Code Implementation

### Backend Changes

#### `logic/internal/api/handlers.go`

**ListZonesHandler** - Returns all zone fields:
```go
func ListZonesHandler(client *redis.Client) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // ... get zone keys ...
        
        zones := []map[string]interface{}{}
        for _, key := range zoneKeys {
            zoneData, err := client.HGetAll(ctx, key)
            if err != nil {
                continue
            }
            zones = append(zones, convertToInterfaceMap(zoneData))
        }
        
        json.NewEncoder(w).Encode(zones)
    }
}
```

**CreateZoneHandler** - Auto-loads climate entity data:
```go
// Auto-load data from climate entity if HA integration is enabled
if climateEntityID != "" && integration != nil && integration.IsEnabled() {
    haClient := integration.GetClient()
    climateState, err := haClient.GetState(ctx, climateEntityID)
    if err == nil {
        // Auto-load current temperature if not explicitly overridden
        if _, hasTempSensor := zone["temperature_sensor_entity_id"]; !hasTempSensor {
            if currentTemp, ok := climateState.Attributes["current_temperature"].(float64); ok {
                zone["current_temperature"] = fmt.Sprintf("%.1f", currentTemp)
            }
        }
        
        // Auto-load target temperature if not provided
        if _, hasTargetTemp := zone["target_temperature"]; !hasTargetTemp {
            if targetTemp, ok := climateState.Attributes["temperature"].(float64); ok {
                zone["target_temperature"] = fmt.Sprintf("%.1f", targetTemp)
            }
        }
    }
}
```

#### `logic/internal/homeassistant/integration.go`

**updateZoneClimate** - Syncs current and target temperature from climate entity:
```go
func (i *Integration) updateZoneClimate(ctx context.Context, entityID, state string, attributes map[string]interface{}) error {
    // Get zone data to check if temperature sensor is configured
    zoneData, err := i.redisClient.HGetAll(ctx, zoneKey)
    if err != nil {
        return err
    }

    // Extract current temperature from climate entity if no temperature sensor
    tempSensorEntity, hasTempSensor := zoneData["temperature_sensor_entity_id"]
    if (!hasTempSensor || tempSensorEntity == "") {
        if currentTemp, ok := attributes["current_temperature"].(float64); ok {
            i.redisClient.HSet(ctx, zoneKey, "current_temperature", currentTemp)
        }
    }

    // Extract target temperature from climate entity
    if targetTemp, ok := attributes["temperature"].(float64); ok {
        // Only update if changed (to avoid loops)
        if math.Abs(targetTemp-currentTarget) > models.DefaultTargetChangeThreshold {
            i.redisClient.HSet(ctx, zoneKey, "target_temperature", targetTemp)
            i.triggerRecalculation(ctx)
        }
    }
    
    return nil
}
```

**syncZoneClimate** - New function for batch sync:
```go
func (i *Integration) syncZoneClimate(ctx context.Context, zoneKey, entityID string) error {
    state, err := i.client.GetState(ctx, entityID)
    if err != nil {
        return err
    }

    updates := make(map[string]interface{})

    // Sync current temperature if no temperature sensor configured
    zoneData, _ := i.redisClient.HGetAll(ctx, zoneKey)
    tempSensorEntity, hasTempSensor := zoneData["temperature_sensor_entity_id"]
    if (!hasTempSensor || tempSensorEntity == "") {
        if currentTemp, ok := state.Attributes["current_temperature"].(float64); ok {
            updates["current_temperature"] = currentTemp
        }
    }

    // Sync target temperature
    if targetTemp, ok := state.Attributes["temperature"].(float64); ok {
        updates["target_temperature"] = targetTemp
    }

    if len(updates) > 0 {
        return i.redisClient.HSet(ctx, zoneKey, updates)
    }

    return nil
}
```

**SyncAllStates** - Updated to sync climate entities:
```go
func (i *Integration) SyncAllStates(ctx context.Context) error {
    // ... get zones ...
    
    for _, key := range zoneKeys {
        zoneData, err := i.redisClient.HGetAll(ctx, key)
        
        // Sync climate entity first (if configured)
        climateEntity, hasClimateEntity := zoneData["climate_entity_id"]
        if hasClimateEntity && climateEntity != "" {
            i.syncZoneClimate(ctx, key, climateEntity)
        }

        // Sync temperature sensor (overrides climate entity if present)
        if sensorEntity, ok := zoneData["temperature_sensor_entity_id"]; ok && sensorEntity != "" {
            i.syncTemperatureSensor(ctx, key, sensorEntity)
        }

        // Sync valve switch
        // ...
    }
    
    return nil
}
```

## Usage Examples

### Example 1: Zone with Climate Entity Only

**Request:**
```bash
curl -X POST http://localhost:8080/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Living Room",
    "climate_entity_id": "climate.living_room",
    "valve_switch_entity_id": "switch.living_room_valve"
  }'
```

**Behavior:**
- System fetches `climate.living_room` state from HA
- Auto-loads current temperature (e.g., 21.5°C)
- Auto-loads target temperature (e.g., 22.0°C)
- Valve switch state synced from HA

### Example 2: Zone with Climate Entity + Temperature Sensor Override

**Request:**
```bash
curl -X POST http://localhost:8080/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bedroom",
    "climate_entity_id": "climate.bedroom",
    "temperature_sensor_entity_id": "sensor.bedroom_accurate_temp",
    "valve_switch_entity_id": "switch.bedroom_valve"
  }'
```

**Behavior:**
- System fetches `climate.bedroom` state from HA
- Uses `sensor.bedroom_accurate_temp` for current temperature (overrides climate entity)
- Auto-loads target temperature from climate entity
- Valve switch state synced from HA

### Example 3: Zone with Manual Configuration

**Request:**
```bash
curl -X POST http://localhost:8080/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Office",
    "temperature_sensor_entity_id": "sensor.office_temp",
    "valve_switch_entity_id": "switch.office_valve",
    "target_temperature": "20.0"
  }'
```

**Behavior:**
- No climate entity, so no auto-loading
- Uses sensor for current temperature
- Uses manual target temperature
- No HA sync for target temperature changes

## Benefits

1. **Simplified Setup**: Users only need to configure climate entity + valve switch
2. **Automatic Sync**: Temperature changes in HA automatically sync to the app
3. **Flexible Override**: Temperature sensor can override climate entity's current temperature
4. **UI Visibility**: All zone data now displayed in the UI
5. **Bi-directional Control**: Changes in either HA or the app sync to the other side

## Migration Guide

### For Existing Zones

Existing zones without `climate_entity_id` continue to work as before. To enable climate entity sync:

1. Edit the zone in the UI
2. Add the climate entity ID
3. Save the zone
4. System will automatically start syncing with the climate entity

### Best Practices

1. **Use Climate Entities**: Configure zones with climate entities for automatic sync
2. **Override When Needed**: Use temperature sensor only when climate entity's current temperature is inaccurate
3. **Always Configure Valve**: Valve switch entity is required for valve control
4. **Check Entity Cache**: After adding/updating climate entity IDs, entity cache is automatically refreshed

## Troubleshooting

### Climate Entity Not Syncing

1. Check that Home Assistant integration is enabled (`GET /api/ha/status`)
2. Verify climate entity ID is correctly formatted (`climate.entity_name`)
3. Check entity cache is populated (`/api/ha/sync` to force sync)
4. Verify WebSocket connection is active

### Temperature Not Updating

1. Check if temperature sensor is configured (it overrides climate entity)
2. Verify climate entity has `current_temperature` attribute in HA
3. Check Redis data: `redis-cli HGETALL multizone:zone:<zone_id>`
4. Check logs for sync errors

### Target Temperature Changes Not Syncing to HA

1. Verify zone has `climate_entity_id` configured
2. Check HA integration is enabled
3. Verify climate entity supports `climate.set_temperature` service
4. Check logs for HA API errors

## API Reference

### Zone Creation

**Endpoint:** `POST /api/zones`

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Zone display name |
| `climate_entity_id` | string | No | HA climate entity ID for auto-loading and sync |
| `temperature_sensor_entity_id` | string | No | HA sensor entity ID for current temperature override |
| `valve_switch_entity_id` | string | No | HA switch entity ID for valve control |
| `target_temperature` | string | No | Manual target temperature (auto-loaded from climate if not provided) |
| `priority` | string | No | Zone priority (0-100, default: 0) |

**Response:**
```json
{
  "status": "created",
  "id": "zone-1234567890"
}
```

### Zone List

**Endpoint:** `GET /api/zones`

**Response:**
```json
[
  {
    "id": "zone-1234567890",
    "name": "Living Room",
    "enabled": "true",
    "current_temperature": "21.5",
    "target_temperature": "22.0",
    "satisfaction": "underheated",
    "valve_state": "open",
    "priority": "50",
    "temperature_sensor_entity_id": "",
    "valve_switch_entity_id": "switch.living_room_valve",
    "climate_entity_id": "climate.living_room"
  }
]
```

## Technical Notes

### Loop Prevention

To prevent infinite loops when syncing temperatures between HA and the app:
- Target temperature changes are only synced if they differ by more than `DefaultTargetChangeThreshold` (0.1°C)
- This threshold is defined in `logic/internal/models/defaults.go`

### Entity Cache

The integration maintains an in-memory cache mapping entity IDs to zone keys:
- `tempSensorToZone`: Temperature sensor entity → zone key
- `valveToZone`: Valve switch entity → zone key
- `climateToZone`: Climate entity → zone key

Cache is automatically refreshed when:
- Integration starts
- Zone entity IDs are updated
- Manual sync is triggered via `/api/ha/sync`

### WebSocket Events

The integration listens to HA WebSocket events for:
- State changes on temperature sensors
- State changes on valve switches
- State changes on main climate entity
- State changes on zone climate entities

Events are routed using the entity cache for O(1) lookup performance.
