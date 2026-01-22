# Multizone Climate for Home Assistant

Advanced multi-zone HVAC management system combining a lightweight Home Assistant add-on with a native custom integration for intelligent zone control, valve management, and optimal temperature coordination.

## Overview

Multizone Climate solves the challenge of managing multiple heating/cooling zones with a single HVAC unit. The system intelligently coordinates per-room temperature control, automatic valve management, and main thermostat settings to optimize comfort and energy efficiency while ensuring HVAC safety.

**Key Capabilities:**
- Per-room temperature control with priority-based allocation
- Intelligent valve management with safety enforcement
- Automatic main climate target temperature calculation
- Native Home Assistant integration with entity selectors
- Event-driven state synchronization
- Background job processing with Redis state management

## The Problem

Many HVAC installations have a single thermostat controlling water temperature based on outdoor conditions, but lack per-room temperature control. This project addresses:

- **Single Main Thermostat**: Controls overall HVAC unit using heating curves
- **Multiple Zones**: Individual rooms need independent temperature control
- **Valve Management**: Each room has a valve (open/close) for heat distribution
- **Safety Requirement**: At least one valve must remain open (no circulating line)
- **Coordination Challenge**: Need intelligent logic to balance all zones while preventing HVAC damage

## Architecture

The system consists of two components that work together:

### 1. Home Assistant Add-on (Backend)

A lightweight 2-container Docker add-on providing the core intelligence:

```
┌─────────────────────────────────────────────┐
│         Home Assistant Add-on               │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────────┐  ┌────────────────┐  │
│  │ Logic Container  │  │ Redis Container│  │
│  │   (GoLang)       │  │   (Bundled)    │  │
│  │                  │  │                │  │
│  │ • Algorithms     │  │ • State Store  │  │
│  │ • Job Queue      │  │ • Config Data  │  │
│  │ • Valve Control  │  │ • Job Queues   │  │
│  │ • Safety Checks  │  │ • Persistence  │  │
│  │ • REST API       │  │                │  │
│  └────────┬─────────┘  └────────────────┘  │
│           │ :8080                           │
└───────────┼─────────────────────────────────┘
            │
            │ HTTP REST API
            ▼
┌─────────────────────────────────────────────┐
│      Home Assistant Custom Integration      │
├─────────────────────────────────────────────┤
│                                             │
│  • Config Flow with Entity Selectors       │
│  • Climate Entities (one per zone)         │
│  • Coordinator (polls for commands)        │
│  • State Sync (pushes temperature updates) │
│                                             │
└─────────────────────────────────────────────┘
            │
            │ Service Calls
            ▼
┌─────────────────────────────────────────────┐
│         Home Assistant Core                 │
│                                             │
│  • Main Climate Entity (existing)          │
│  • Temperature Sensors (existing)          │
│  • Valve Switches (existing)               │
└─────────────────────────────────────────────┘
```

**Logic Container (GoLang):**
- Main target temperature calculation
- Valve management algorithms
- Safety enforcement (minimum valves open)
- Priority-based zone sorting
- State machine for zone satisfaction
- Open-first-then-close valve sequencing
- Background job processing
- REST API endpoint (port 8080)

**Redis Container:**
- Zone configurations and states
- Job queues (calculate temp, update valves, safety check)
- Valve locks and timestamps
- Historical metrics

### 2. Home Assistant Custom Integration

Native Python integration providing the user interface and entity management:

- **Config Flow**: Multi-step setup wizard with searchable entity selectors
- **Climate Entities**: One climate entity created per zone
- **Coordinator**: Polls backend for commands (configurable interval)
- **Event-Driven Sync**: Pushes temperature sensor changes to backend
- **Service Execution**: Executes commands from backend (set temperature, valve control)

## Quick Start

### Prerequisites

- Home Assistant OS or Supervised installation
- Temperature sensors integrated with Home Assistant
- Switch or valve entities for room valves
- Main climate entity for your HVAC thermostat

### Step 1: Install the Add-on

1. **Add Repository**:
   - Go to **Settings** → **Add-ons** → **Add-on Store** → ⋮ (menu) → **Repositories**
   - Add: `https://github.com/Chester929/ha_multizone_climate`

2. **Install Add-on**:
   - Find "Multizone Climate" in the add-on store
   - Click **INSTALL**
   - Wait for installation to complete

3. **Configure Add-on** (optional):
   - Go to the **Configuration** tab
   - Adjust settings if needed:
     ```yaml
     integration:
       coordinator_interval: 30  # Polling interval in seconds (5-300)
       backend_port: 8080         # Backend API port
     redis:
       mode: bundled              # Use bundled Redis or external
       password: ""               # Redis password (optional)
     logic:
       log_level: "info"          # Logging level: debug, info, warning, error
     ```

4. **Start the Add-on**:
   - Go to the **Info** tab
   - Click **START**
   - Wait for the add-on to start successfully
   - The add-on will automatically install the custom integration to `/config/custom_components/`
   - Check the **Log** tab to verify:
     - "Custom component installed successfully!" message appears
     - Containers are running properly

5. **Restart Home Assistant**:
   - Go to **Settings** → **System** → **Restart**
   - After restart, the Multizone Climate integration will be available
   - No manual file copying required!

### Step 2: Configure Zones

1. **Add Integration**:
   - Go to **Settings** → **Devices & Services**
   - Click **+ ADD INTEGRATION**
   - Search for "Multizone Climate"
   - Click to start setup wizard

2. **Select Main Climate** (Step 1):
   - Use the entity selector to choose your main HVAC climate entity
   - Example: `climate.main_thermostat`
   - This is your existing thermostat that controls the whole HVAC system
   - Click **SUBMIT**

2. **Configure First Zone** (Step 2):
   - **Zone Name**: Enter a descriptive name (e.g., "Bedroom")
   - **Temperature Sensor**: Select the temperature sensor for this room
     - Entity selector shows only temperature sensors
     - Example: `sensor.bedroom_temperature`
   - **Valve Switch**: Select the switch/valve entity for this room
     - Entity selector shows switch and valve entities
     - Example: `switch.bedroom_valve`
   - **Target Temperature**: Set desired temperature (°C, default: 20.0)
   - **Priority**: Set zone priority (0-100, default: 50)
     - Higher priority zones get preference during heating/cooling
   - Click **SUBMIT**

3. **Add More Zones** (Optional):
   - After submitting the first zone, you'll be prompted to add another zone
   - Click **SUBMIT** to add more zones, or **FINISH** when done
   - Repeat for each room you want to control

4. **Verify Setup**:
   - Go to **Settings** → **Devices & Services** → **Multizone Climate**
   - You should see:
     - One device: "Multizone Climate"
     - Climate entities: One per zone (e.g., `climate.multizone_bedroom`)
     - All entities grouped under the same device

### Step 3: Use Your Zones

Each zone now has a climate entity that you can:

- **View in Dashboard**: Add climate cards to your Lovelace dashboard
- **Set Target Temperature**: Adjust target temp directly on the climate entity
- **Monitor Status**: See current temperature, target, and HVAC mode
- **Automation**: Use in automations and scripts

**The system automatically:**
- Monitors temperature sensors in real-time
- Calculates optimal main thermostat temperature
- Opens/closes valves based on zone demands
- Ensures at least one valve stays open (safety)
- Executes all commands through the integration

## Core Features

### Intelligent Zone Management
- **Per-Room Control**: Independent temperature targets for each zone
- **Priority System**: Higher priority zones get preference (0-100 scale)
- **State Machine**: Tracks zone satisfaction states (satisfied, cooling, warming)
- **Hysteresis**: Prevents valve chattering with configurable thresholds
- **Automatic Valve Control**: Opens/closes valves based on demand

### Safety Features
- **Minimum Valves Open**: Configurable minimum (prevents HVAC damage)
- **Open-First-Then-Close**: Ensures new valves open before others close
- **Valve Actuation Delays**: Prevents wear from rapid switching
- **Fallback Valve**: Automatic activation when all zones satisfied
- **Error Recovery**: Graceful handling of sensor/valve failures

### Main Climate Optimization
- **Automatic Calculation**: Determines optimal thermostat temperature
- **Calculation Modes**: Slider-based or average of unsatisfied zones
- **Zone Exclusion**: Ignores overheated zones from calculation
- **Priority Weighting**: Considers zone priorities in decisions

### Integration Features
- **Native Entity Selectors**: Searchable dropdowns filtered by entity type
- **Event-Driven Updates**: Real-time temperature sync to backend
- **Command Polling**: Configurable coordinator interval (5-300 seconds)
- **Retry Logic**: Robust error handling with automatic retries
- **Device Grouping**: All zones under one device in Home Assistant

## Configuration Reference

### Add-on Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `integration.coordinator_interval` | integer | 30 | How often integration polls for commands (5-300 seconds) |
| `integration.backend_port` | integer | 8080 | Backend API port (1024-65535) |
| `redis.mode` | string | bundled | Use `bundled` Redis or `external` server |
| `redis.host` | string | - | External Redis host (if mode=external) |
| `redis.port` | integer | 6379 | External Redis port (if mode=external) |
| `redis.password` | string | "" | Redis password (optional) |
| `logic.log_level` | string | info | Logging level: debug, info, warning, error |

### Zone Configuration Fields

- **Zone Name**: Friendly name for the zone
- **Temperature Sensor**: Entity with `device_class: temperature`
- **Valve Switch**: Switch or valve entity controlling the zone valve
- **Target Temperature**: Desired temperature in °C (adjustable anytime)
- **Priority**: Zone importance (0=lowest, 100=highest, default=50)

**Note:** Advanced valve control parameters (temperature offsets for opening/closing valves, fallback valve selection) are managed internally by the backend and not currently configurable through the UI.

## Technology Stack

- **Backend Logic**: GoLang
  - High performance and low resource usage
  - Excellent concurrency with goroutines
  - Strong typing and compile-time checks
  
- **Custom Integration**: Python 3
  - Native Home Assistant integration
  - Config flow for easy setup
  - Entity selectors with filtering
  
- **State Management**: Redis
  - Fast in-memory storage
  - Persistence with append-only file
  - Simple pub/sub and queuing

- **Deployment**: Docker
  - Multi-architecture support (amd64, armv7, aarch64)
  - Home Assistant add-on supervisor integration
  - Automatic health checks and restarts

## System Requirements

- **Home Assistant**: OS or Supervised installation
- **RAM**: Minimum 512MB (1GB recommended)
- **Architectures**: amd64, armv7, aarch64
- **Network**: Local network access between add-on and Home Assistant
- **Entities**: Temperature sensors, valve switches, main climate entity

## Documentation

- **[DIAGRAMS.md](DIAGRAMS.md)**: System architecture and flow diagrams
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Implementation guide and deployment
- **[VALVE_MANAGEMENT.md](VALVE_MANAGEMENT.md)**: Valve control algorithms and safety
- **[STATISTICS_API.md](STATISTICS_API.md)**: Statistics and metrics API
- **[DOCKER_BUILDS.md](DOCKER_BUILDS.md)**: Multi-architecture build documentation

## Troubleshooting

### Add-on Won't Start

1. Check the add-on logs for errors
2. Verify Redis is running (if using external Redis)
3. Ensure port 8080 is not in use
4. Check system resources (RAM, disk space)

### Integration Can't Connect to Backend

1. Ensure the add-on is started and running
2. Check add-on logs for backend errors
3. Verify `backend_port` setting matches (default: 8080)
4. Check Home Assistant logs for connection errors

### Commands Not Executing

1. Check coordinator interval setting (might be too long)
2. Verify entities exist and are accessible
3. Check for retry errors in integration logs
4. Ensure backend is calculating commands (check add-on logs)

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug
```

Then check Home Assistant logs for detailed information.

## Contributing

Contributions are welcome! Please:
- Fork the repository
- Create a feature branch
- Submit pull requests
- Follow existing code style
- Add tests for new features

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

MIT License - See [LICENSE](LICENSE) file for details

## Support

- **Issues**: [GitHub Issues](https://github.com/Chester929/ha_multizone_climate/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Chester929/ha_multizone_climate/discussions)
- **Documentation**: This README and linked documentation files

## Related Projects

- [remeha_home_by_chester](https://github.com/Chester929/remeha_home_by_chester) - Remeha HVAC thermostat integration for Home Assistant

## Frequently Asked Questions

### Does this create new entities in Home Assistant?

Yes! The custom integration creates one climate entity per configured zone (e.g., `climate.multizone_bedroom`). These are grouped under a single "Multizone Climate" device. Your existing temperature sensors, valve switches, and main climate entity remain unchanged - the integration just references and controls them.

### How does the system communicate?

The flow is: **Temperature Sensor** → **Climate Entity** → **Backend API** (calculations) → **Coordinator** (polls for commands) → **Service Calls** (executes on valves/thermostat)

All communication between the integration and backend happens via REST API over HTTP on localhost.

### What if all zones are satisfied and want to close their valves?

The backend enforces a configurable minimum number of valves that must stay open. When all zones are satisfied, the system automatically activates a designated fallback valve to maintain circulation and prevent HVAC damage.

### Can I use this with any HVAC system?

Yes, as long as you have:
- A main climate entity in Home Assistant (any thermostat/HVAC controller)
- Temperature sensors for each room
- Switch or valve entities to control room valves

The system is brand-agnostic and works with any compatible entities.

### How do I adjust zone priorities?

You can set priorities during initial setup (0-100 scale). To change later, you'll need to reconfigure the integration or adjust the zone configuration. Higher priority zones get preference when the system needs to make decisions about which zones to heat/cool first.

### What happens if a temperature sensor fails?

The system gracefully handles sensor failures. If a sensor becomes unavailable, the zone's last known temperature is used, and warnings are logged. The system continues to operate other zones normally.

### Can I run the backend outside of the Home Assistant add-on?

Yes, you can run the Logic and Redis containers standalone using `docker-compose.yml`. However, you'll need to configure the integration to point to the correct backend URL, and you won't get the convenience of Home Assistant add-on management.
