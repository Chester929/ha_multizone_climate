# Multizone Climate - Custom Integration

Home Assistant custom integration for managing multizone climate control with intelligent valve management and backend coordination.

## Features

✅ **Searchable Entity Selectors**: Easy configuration with dropdowns filtered by entity type
✅ **Device Hierarchy**: All zones grouped under a single device in Home Assistant
✅ **Event-Driven State Sync**: Automatically pushes temperature updates to backend
✅ **Backend Coordination**: Commands calculated by backend and executed automatically
✅ **Configurable Polling**: Coordinator interval adjustable in addon settings (5-300s)
✅ **Climate Entities**: Each zone creates a full climate entity with target temperature control
✅ **Temperature Device Class**: Sensor selectors filtered to temperature sensors only

## Installation

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add this repository URL
6. Install "Multizone Climate"
7. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `custom_components/multizone_climate` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Setup

1. **Install and Start the Addon** first (backend must be running)
2. Go to **Settings** → **Devices & Services**
3. Click **"+ ADD INTEGRATION"**
4. Search for "Multizone Climate"
5. Follow the configuration wizard:
   - **Step 1**: Select your main climate entity
   - **Step 2**: Configure zone:
     - Zone name (text field)
     - Temperature sensor (entity selector - temperature sensors only)
     - Valve switch (entity selector - accepts switch or valve entities)
     - Target temperature (°C, default: 20.0)
     - Priority (0-100, default: 50)

   > **Note:** The integration creates a new climate entity for each zone. Opening/closing offsets and fallback valve behavior are managed internally by the backend and are not currently configurable through the UI.

6. After setup, you'll see:
   - A new climate entity for the zone (`climate.multizone_{zone_name}`)
   - Grouped under the "Multizone Climate" device

## Architecture

### Integration Components

**Config Flow**: Multi-step configuration with entity selectors
**Climate Platform**: Creates climate entities for zones, monitors sensors
**Coordinator**: Polls backend for commands and executes them

### Data Flow

```
Temperature Sensor Changes (20.5°C → 21.0°C)
    ↓
Climate Entity detects change
    ↓
POST /api/integration/state_update to backend
    ↓
Backend calculates new target temps & valve states
    ↓
Coordinator polls GET /api/integration/commands (every 30s)
    ↓
Executes commands (set_temperature, turn_on/off)
    ↓
DELETE /api/integration/commands (acknowledges)
```

## Entity Domain Filtering

- **Main Climate Entity**: `climate` domain only
- **Temperature Sensor**: `sensor` domain with `device_class="temperature"`
- **Valve Switch**: Both `switch` AND `valve` domains
- **No zone climate entity option** - integration creates zone entities

## Created Entities

For each zone, the integration creates:

**Climate Entity**: `climate.multizone_{zone_name}`
- Current temperature (from configured sensor)
- Target temperature (user adjustable)
- HVAC modes: HEAT, OFF
- Attributes: zone_id, sensors, offsets, priority, etc.

## Backend Communication

The integration connects to the Go backend addon at `http://localhost:8080`.

**API Endpoints**:
1. `POST /api/integration/state_update` - Push temperature updates
2. `GET /api/integration/commands` - Poll for commands
3. `DELETE /api/integration/commands` - Acknowledge execution

**Coordinator Interval**: Set via addon configuration (default: 30 seconds)

## Debugging

Enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug
```

## Version

**2.0.0** - Full integration with backend coordination, entity selectors, and climate platform
