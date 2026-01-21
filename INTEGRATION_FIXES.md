# Multi-zone Climate Integration Fixes

## Summary

This document describes the fixes and improvements made to enable proper climate entity integration between Home Assistant and the multi-zone climate control application.

## Issues Fixed

### 1. Climate Entity Integration in Zone Configuration

**Problem**: The backend supported `climate_entity_id` for zones, but the frontend UI didn't expose this field.

**Solution**:
- Updated `Zone` interface in TypeScript to include all zone fields:
  - `temperature_sensor_entity_id`
  - `valve_switch_entity_id`
  - `climate_entity_id` (new)
  - `opening_offset`, `closing_offset`
  - `is_fallback_valve`
  - `target_change_threshold`

- Enhanced `ZoneCard` component to show all entity configuration fields in edit mode
- Added helper text explaining the purpose of climate entity linking

**Files Modified**:
- `frontend/src/client/types/index.ts`
- `frontend/src/client/components/ZoneCard.tsx`
- `frontend/src/client/components/App.tsx` (add climate_entity_id to zone creation)

### 2. Home Assistant Climate Entity State Synchronization

**Problem**: Changes to zone climate entity target temperatures in Home Assistant were not being synchronized to the application.

**Solution**:
- Added climate entity to zone mapping in entity cache (`climateToZone` map)
- Implemented `updateZoneClimate()` method to handle climate entity state changes
- Enhanced `handleStateChange()` to detect and process zone climate entity updates
- Added bidirectional sync: HA → Application

**Implementation Details**:
```go
// When climate entity temperature attribute changes in HA
if targetTemp, ok := attributes["temperature"].(float64); ok {
    // Update zone target temperature in Redis
    redisClient.HSet(ctx, zoneKey, "target_temperature", targetTemp)
    // Trigger recalculation
    triggerRecalculation(ctx)
}
```

**Files Modified**:
- `logic/internal/homeassistant/integration.go`

### 3. Application to Home Assistant Climate Entity Updates

**Problem**: When zone target temperature was changed via the frontend UI, the linked climate entity in Home Assistant was not updated.

**Solution**:
- Implemented `SetZoneClimateTemperature()` method to push target temp changes to HA
- Updated `UpdateZoneHandler` to call this method when target temperature changes
- Added entity cache refresh when entity IDs are modified

**Implementation Details**:
```go
func (i *Integration) SetZoneClimateTemperature(ctx context.Context, zoneKey string) error {
    // Get zone's climate entity ID and target temperature
    zoneData := redisClient.HGetAll(ctx, zoneKey)
    climateEntityID := zoneData["climate_entity_id"]
    targetTemp := zoneData["target_temperature"]
    
    // Update HA climate entity
    client.SetTemperature(ctx, climateEntityID, targetTemp)
}
```

**Files Modified**:
- `logic/internal/homeassistant/integration.go`
- `logic/internal/api/handlers.go`
- `logic/cmd/server/main.go`

### 4. Global Configuration UI Improvements

**Problem**: ConfigManager UI only showed a subset of available global configuration options.

**Solution**:
- Updated `ALLOWED_CONFIG_KEYS` to match backend `GlobalConfig` model:
  - `main_climate_entity_id`
  - `main_target_all_zones_satisfied`
  - `use_average_mode` (slider vs average calculation)
  - `slider_position`
  - `min_valves_open`
  - `main_min_temp`, `main_max_temp`
  - `main_change_threshold`
  - `valve_actuation_delay`
  - `coordinator_interval`
  - `satisfaction_eps`

- Organized UI into logical sections:
  - Main Climate Entity
  - Temperature Calculation Settings
  - Temperature Limits
  - Valve Management
  - Advanced Settings

- Added proper validation for boolean, numeric, and integer fields
- Added helper text explaining each configuration option

**Files Modified**:
- `frontend/src/client/components/ConfigManager.tsx`

### 5. Entity Cache Refresh and State Sync

**Problem**: No easy way to refresh entity cache after configuration changes or synchronize all states from Home Assistant.

**Solution**:
- Added "Sync States & Refresh Cache" button to IntegrationConfig component
- Calls `/api/ha/sync` endpoint which:
  - Synchronizes all temperature sensors
  - Synchronizes all valve switches
  - Synchronizes main climate entity
  - Rebuilds entity cache with updated mappings

**Files Modified**:
- `frontend/src/client/components/IntegrationConfig.tsx`

## Configuration Flow

### Redis as Primary Configuration Store

The application follows the pattern: **Redis First, YAML Fallback**

1. **Startup**:
   - Backend loads integration settings from Redis (`multizone:integrations`)
   - Overrides environment variables if Redis settings exist
   - Builds entity cache from zone configurations

2. **Configuration Changes**:
   - All changes made via frontend are stored directly in Redis
   - No YAML file modifications needed
   - Changes take effect immediately or after sync/restart

3. **YAML Files** (examples/zones-config.yaml):
   - Serve as examples and documentation
   - Can be imported into Redis for initial setup
   - Not actively monitored or loaded during runtime

### Configuration Keys in Redis

```
multizone:config                          # Global configuration
  - main_climate_entity_id
  - main_target_all_zones_satisfied
  - use_average_mode
  - slider_position
  - min_valves_open
  - main_min_temp
  - main_max_temp
  - main_change_threshold
  - valve_actuation_delay
  - coordinator_interval
  - satisfaction_eps

multizone:zone:{zone_id}                  # Per-zone configuration
  - id
  - name
  - enabled
  - temperature_sensor_entity_id
  - valve_switch_entity_id
  - climate_entity_id                     # NEW: Link to HA climate entity
  - target_temperature
  - current_temperature
  - satisfaction
  - valve_state
  - priority
  - opening_offset
  - closing_offset
  - is_fallback_valve
  - target_change_threshold

multizone:integrations                    # Integration settings
  - ha_enabled
  - ha_base_url
  - ha_token
  - ha_websocket
  - mqtt_enabled
  - mqtt_broker
  - mqtt_port
  - mqtt_username
  - mqtt_password
```

## How Climate Entity Integration Works

### Scenario 1: User Changes Temperature in Home Assistant

1. User adjusts climate entity temperature in HA: `climate.bedroom` → 22°C
2. HA WebSocket sends `state_changed` event
3. Integration's `handleStateChange()` receives event
4. Checks if entity is in `climateToZone` cache
5. Updates zone target temperature in Redis: `multizone:zone:bedroom`
6. Triggers main temperature recalculation job
7. Frontend receives update via WebSocket and refreshes UI

### Scenario 2: User Changes Temperature in Frontend UI

1. User adjusts slider in ZoneCard: Bedroom → 22°C
2. Frontend calls `PUT /api/zones/bedroom` with new target_temperature
3. `UpdateZoneHandler` validates and saves to Redis
4. Handler calls `SetZoneClimateTemperature()` if climate entity is linked
5. Integration calls HA API: `climate.set_temperature` on `climate.bedroom`
6. HA updates its climate entity state
7. WebSocket event flows back (Scenario 1), creating confirmation loop

### Scenario 3: Initial Sync

1. User clicks "Sync States & Refresh Cache" button
2. Frontend calls `POST /api/ha/sync`
3. Integration calls `SyncAllStates()`:
   - Queries HA for all zone temperature sensors
   - Queries HA for all zone valve switches
   - Queries HA for main climate entity
   - Updates all values in Redis
4. Rebuilds entity cache with any new entity mappings
5. Returns success message to frontend

## Testing

### Go Backend Tests
All existing tests pass:
```bash
cd logic && go test ./...
# PASS: algorithm (temperature, valve, satisfaction tests)
# PASS: homeassistant (client, integration tests)
# PASS: statistics (tracker, metrics tests)
```

### Frontend Tests
48 out of 49 tests pass:
```bash
cd frontend && npm test
# PASS: App, ConfigManager, IntegrationConfig, ZoneCard, TemperatureChart
# 1 test with pre-existing issue (unrelated to our changes)
```

### Build Verification
Both backend and frontend build successfully:
```bash
cd logic && go build ./...        # Success
cd frontend && npm run build      # Success
```

## Best Practices for Users

### Setting Up Climate Entity Integration

1. **Configure Integration Settings**:
   - Go to "Integrations" tab
   - Enable Home Assistant integration
   - Enter HA base URL and access token
   - Enable WebSocket for real-time updates
   - Save and test connection

2. **Link Zones to Climate Entities**:
   - Edit each zone in "Zones" tab
   - Fill in temperature sensor entity ID (required)
   - Fill in valve switch entity ID (required)
   - Fill in climate entity ID (optional, for sync)
   - Save changes

3. **Sync Initial States**:
   - Go to "Integrations" tab
   - Click "Sync States & Refresh Cache"
   - Verify zones show current temperatures

4. **Configure Global Settings**:
   - Go to "Configuration" tab
   - Set main climate entity ID
   - Configure temperature limits and calculation mode
   - Set valve management parameters
   - Save configuration

### Troubleshooting

**Problem**: Climate entity not updating when I change temperature in frontend
- **Check**: Is climate_entity_id configured for the zone?
- **Check**: Is Home Assistant integration enabled and connected?
- **Check**: Is the entity ID correct? (use format: `climate.zone_name`)

**Problem**: Frontend temperature not updating when I change HA climate entity
- **Check**: Is WebSocket enabled in integration settings?
- **Check**: Is the entity cache up to date? (click "Sync States & Refresh Cache")
- **Check**: Look at browser console and backend logs for errors

**Problem**: Entity cache not finding my entities
- **Solution**: After adding or changing entity IDs, click "Sync States & Refresh Cache"
- **Solution**: Restart the logic container to rebuild cache from Redis

## Future Enhancements

Potential improvements for future consideration:

1. **Automatic Cache Refresh**: Auto-refresh entity cache when zones are created/modified
2. **Bi-directional Valve Control**: Allow HA to control valves directly via MQTT
3. **Climate Entity Creation**: Auto-create climate entities in HA for each zone
4. **Configuration Import/Export**: Import/export full configuration as YAML/JSON
5. **Health Dashboard**: Show entity connectivity status and last update times
6. **Zone Groups**: Group multiple zones for unified control
7. **Scheduling**: Time-based temperature profiles for each zone

## References

- **Backend Models**: `logic/internal/models/models.go`
- **HA Integration**: `logic/internal/homeassistant/integration.go`
- **API Handlers**: `logic/internal/api/handlers.go`
- **Frontend Types**: `frontend/src/client/types/index.ts`
- **Zone UI**: `frontend/src/client/components/ZoneCard.tsx`
- **Config UI**: `frontend/src/client/components/ConfigManager.tsx`
- **Integration UI**: `frontend/src/client/components/IntegrationConfig.tsx`

## Deployment Notes

### Frontend Build Requirements

The frontend requires `node_modules` to be installed before building:

```bash
cd frontend
npm install
npm run build
```

This is standard for Node.js/React applications and not a code issue. The build process:
1. Installs dependencies from `package.json` into `node_modules/`
2. Compiles TypeScript and React components
3. Bundles client and server code into `dist/`

For production deployments:
- Use multi-stage Docker builds to keep the final image lean
- Install only production dependencies with `npm ci --production`
- The `node_modules/` directory should be in `.gitignore` (already configured)

### Default Values

Configuration default values are now centralized:
- **Backend**: Defined in `logic/internal/models/defaults.go`
- **Frontend**: Fetched from `/api/defaults` endpoint via `useDefaults` hook
- **UI Components**: Use fetched defaults as fallback values

This ensures consistency between backend and frontend without hardcoding values in multiple places.
