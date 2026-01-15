# ha_multizone_climate
Home Assistant Add-on for advanced multi-zone HVAC management.

## Overview

This project provides a complete solution for managing multiple heating/cooling zones in your Home Assistant setup through a modern, containerized architecture. The system intelligently coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency.

## Documentation

For comprehensive system diagrams and architecture documentation, see [DIAGRAMS.md](DIAGRAMS.md).

A PDF version of the diagrams is automatically generated when DIAGRAMS.md is updated in the `master` or `dev` branches. You can download the latest version from the [GitHub Actions artifacts](../../actions/workflows/generate-diagrams-pdf.yml), or access it directly from the repository root as `diagrams.pdf` after generation.

## The Problem

I have an HVAC unit driven by one thermostat using a heating curve to calculate the correct temperature in pipes. I would like to manage temperature per room using sensors and valve controllers. The HVAC is missing a circulating line, so there has to be at least one valve still open.

### Main Climate Unit and Thermostat

- HVAC unit controlled by one thermostat through physical cables
- Thermostat placed in corridor with its own temperature sensor
- Uses heating curve to calculate water temperature based on outdoor temperature
- Thermostat can be controlled remotely through cloud API (WiFi connected)
- Existing custom component: https://github.com/Chester929/remeha_home_by_chester
- Controls: target temperature and HVAC mode (OFF/Anti-Freeze, Manual, Scheduler)

### Heat Zones

- Temperature sensors in rooms integrated with Home Assistant
- Heat pipe valves (open/close) for each room controlled remotely via switch entities
- Need intelligent coordination to prevent all valves from closing (safety requirement)

## Architecture v2.0 - Containerized Microservices

This project uses a modern microservices architecture with the following containers:

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant Add-on                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  Logic Container │  │ Frontend WebApp  │  │    Redis     │ │
│  │    (GoLang)      │  │  (TypeScript)    │  │  (Optional)  │ │
│  │                  │  │                  │  │              │ │
│  │  • Core Logic    │  │  • Zone Mgmt     │  │  • State     │ │
│  │  • Algorithms    │  │  • Statistics    │  │  • Config    │ │
│  │  • Valve Control │  │  • Metrics       │  │  • Queues    │ │
│  │  • Safety Checks │  │  • Configuration │  │              │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           │                     │                    │         │
│           └─────────────────────┴────────────────────┘         │
│                                 │                              │
│                          ┌──────▼──────┐                       │
│                          │    Redis    │                       │
│                          │   (Shared)  │                       │
│                          └──────┬──────┘                       │
│                                 │                              │
│           ┌─────────────────────┴────────────────────┐         │
│           │                                          │         │
│  ┌────────▼─────────┐                     ┌──────────▼──────┐ │
│  │  MQTT Middleware │                     │  Auto-Install   │ │
│  │   (Optional)     │                     │   Integration   │ │
│  │                  │                     │   (HA Custom)   │ │
│  │  Redis ←→ MQTT   │                     └─────────────────┘ │
│  └────────┬─────────┘                                         │
│           │                                                   │
└───────────┼───────────────────────────────────────────────────┘
            │
            │ MQTT over TCP
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Home Assistant                             │
│                                                                 │
│  • Climate Entities (zones + main)                             │
│  • Sensor Entities (temperatures, states)                      │
│  • Binary Sensor Entities (valve states)                       │
│  • Switch Entities (zone enable/disable)                       │
│  • Automations & Scripts                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Container Breakdown

#### 1. Logic Container (GoLang)
**Purpose:** Core business logic and algorithms

**Responsibilities:**
- Main target temperature calculation
- Valve management and safety checks
- Background job processing
- State machine for zone satisfaction
- Priority-based zone sorting
- Safety enforcement (minimum valves open)
- Open-first-then-close valve sequencing

**Technology:** GoLang for performance, concurrency, and low resource usage

**Communication:**
- Reads/writes state to Redis
- Publishes events to MQTT (if enabled)

#### 2. Frontend WebApp (TypeScript)
**Purpose:** User interface for management and monitoring

**Responsibilities:**
- Zone management (add, edit, delete zones)
- Thermostat configuration
- Real-time statistics and metrics
- Configuration interface for MQTT integration
- Visual dashboards for monitoring
- Historical data visualization

**Technology:** TypeScript with modern web framework

**Features:**
- Responsive design
- Real-time updates via WebSocket/SSE
- Interactive charts and graphs
- Mobile-friendly interface

**Communication:**
- Reads/writes configuration to Redis
- Displays real-time data from Redis
- Manages MQTT settings

#### 3. Redis Container (Optional)
**Purpose:** Data persistence and message queuing

**Can be:**
- Included in add-on (bundled container)
- External service (user-provided)

**Stores:**
- Global configuration
- Zone states and configurations
- Job queues (calculate temp, update valves, safety check)
- Valve locks and timestamps
- Historical metrics
- MQTT connection settings

#### 4. MQTT Middleware (Optional)
**Purpose:** Bridge between Redis state and Home Assistant

**Functionality:**
- Reads zone/valve/sensor states from Redis
- Publishes to MQTT topics (similar to zigbee2mqtt)
- Subscribes to Home Assistant commands
- Updates Redis based on MQTT commands
- Auto-discovery for Home Assistant entities

**Enabled when:** User configures MQTT integration in frontend

**Exposes to Home Assistant:**
- Climate entities (one per zone + main)
- Temperature sensor entities
- Binary sensor entities (valve states, satisfaction states)
- Switch entities (zone enable/disable, multizone enable)
- Diagnostic sensors (job status, errors)

**Inspiration:** zigbee2mqtt pattern
- `homeassistant/` prefix for discovery
- `multizone/` prefix for state/command topics
- JSON payloads for entity states

#### 5. Auto-Install Integration (Python)
**Purpose:** Optional HA custom integration for direct API access

**Alternative to MQTT:**
- Direct Python integration installed automatically
- Communicates with Logic container via HTTP API or Redis
- Provides same entities as MQTT approach
- For users who prefer native integration over MQTT

## Installation Methods

### Method 1: Home Assistant Add-on (Recommended)

Install as a multi-container add-on:

1. Add repository to Home Assistant add-on store
2. Install "Multizone Climate" add-on
3. Configure options:
   - Redis: Bundled or external
   - MQTT: Enable/disable and configure broker
   - Logic settings: algorithms, thresholds
4. Access frontend WebApp at add-on URL
5. Configure zones through web interface
6. (If MQTT enabled) Entities auto-discovered in Home Assistant
7. (If custom integration) Integration auto-installed

### Method 2: Standalone Containers

For advanced users running Home Assistant Container/Core:

1. Deploy containers separately:
   - `multizone-logic:latest` (GoLang)
   - `multizone-frontend:latest` (TypeScript)
   - `redis:latest` (if not using external)
   - `multizone-mqtt:latest` (if using MQTT)
2. Configure via environment variables or config files
3. Connect to MQTT broker or install custom integration

## Project Goals

1. **Clean Architecture:** Microservices with clear separation of concerns
2. **Performance:** GoLang backend for speed and low resource usage
3. **User Experience:** Modern TypeScript frontend with real-time updates
4. **Flexibility:** MQTT or direct integration options
5. **Safety:** Minimum valve enforcement, delay sequencing, error handling
6. **Observability:** Comprehensive metrics, logging, and debugging
7. **Maintainability:** Well-documented, tested, type-safe code

## Core Features

### Intelligent Zone Management
- Per-room temperature targets
- Automatic valve control based on satisfaction states
- Priority-based heating/cooling allocation
- Hysteresis to prevent valve chattering

### Safety Features
- Minimum valves open enforcement (prevents HVAC damage)
- Open-first-then-close valve sequencing
- Valve actuation delays to prevent wear
- Automatic fallback valve activation
- Comprehensive error handling and recovery

### Main Climate Optimization
- Calculates optimal main thermostat temperature
- Slider-based or average calculation modes
- Accounts for all zone demands
- Excludes overheated zones from calculation

### Advanced Features
- Background job processing with locks
- Redis-backed state management
- Configurable timing and thresholds
- Multi-language support (EN, CZ, SK, PL planned)
- Real-time statistics and metrics
- Historical data tracking

### MQTT Integration (Optional)
- zigbee2mqtt-style topic structure
- Home Assistant auto-discovery
- JSON payloads for all entities
- Bidirectional communication
- State synchronization

## Technology Stack

- **Backend Logic:** GoLang
  - High performance
  - Excellent concurrency (goroutines)
  - Low memory footprint
  - Strong typing
  
- **Frontend:** TypeScript
  - Type safety
  - Modern frameworks (React/Vue/Svelte)
  - Real-time updates
  - Responsive design

- **State Management:** Redis
  - Fast in-memory storage
  - Pub/sub capabilities
  - Persistence options
  - Cluster support

- **Integration:** MQTT or Python
  - MQTT: Industry standard, widely supported
  - Python: Native Home Assistant integration
  - Both: User choice based on preference

## Configuration Example

### Add-on Configuration
```yaml
redis:
  mode: bundled  # or 'external'
  host: localhost  # if external
  port: 6379
  password: ""
  
mqtt:
  enabled: true
  broker: homeassistant.local
  port: 1883
  username: mqtt_user
  password: mqtt_pass
  discovery_prefix: homeassistant
  topic_prefix: multizone

logic:
  coordinator_interval: 15  # seconds
  valve_actuation_delay: 120  # seconds
  main_change_threshold: 0.5  # °C
  
frontend:
  port: 8099
  auth: basic  # or 'none'
  
custom_integration:
  auto_install: true
```

### Frontend Configuration
- Access web interface at `http://homeassistant.local:8099`
- Configure zones (name, temp sensor, valve switch, offsets)
- Set main climate entity and parameters
- View real-time statistics and metrics
- Enable/disable MQTT integration
- Configure MQTT broker settings

## Development Roadmap

### Phase 1: Foundation
- [ ] GoLang logic container with core algorithms
- [ ] Redis integration and state management
- [ ] Basic job processing and queue system
- [ ] Safety checks and valve management

### Phase 2: Frontend
- [ ] TypeScript web application
- [ ] Zone management UI
- [ ] Configuration interface
- [ ] Real-time monitoring dashboard

### Phase 3: Integration
- [ ] MQTT middleware container
- [ ] Home Assistant entity discovery
- [ ] Bidirectional MQTT communication
- [ ] Auto-install custom integration (alternative to MQTT)

### Phase 4: Enhancement
- [ ] Statistics and historical data
- [ ] Advanced metrics and analytics
- [ ] Custom lovelace cards
- [ ] Additional language translations
- [ ] Mobile app (optional)

### Phase 5: Production
- [ ] Comprehensive testing
- [ ] Documentation completion
- [ ] CI/CD pipelines
- [ ] Multi-architecture builds
- [ ] Performance optimization

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## License

MIT License - See LICENSE file for details

## Support

- **Issues:** https://github.com/Chester929/ha_multizone_climate/issues
- **Documentation:** See README.md and DIAGRAMS.md
- **Community:** Home Assistant Community Forum

## Related Projects

- [remeha_home_by_chester](https://github.com/Chester929/remeha_home_by_chester) - Main climate thermostat custom component
- [zigbee2mqtt](https://github.com/Koenkk/zigbee2mqtt) - MQTT bridge inspiration

## Hardware Requirements

- Home Assistant OS/Supervised installation (for add-on)
- Minimum 512MB RAM (1GB recommended)
- Supported architectures: amd64, armv7, aarch64
- Optional: External Redis server
- Optional: MQTT broker (Mosquitto recommended)
