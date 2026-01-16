# ha_multizone_climate
Home Assistant Add-on for advanced multi-zone HVAC management.

## Overview

This project provides a complete solution for managing multiple heating/cooling zones in your Home Assistant setup through a modern, containerized architecture. The system intelligently coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency.

## Documentation

- **[DIAGRAMS.md](DIAGRAMS.md)**: Comprehensive system diagrams and architecture documentation
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Detailed implementation guide, API documentation, and deployment instructions
- **PDF Diagrams**: Automatically generated from DIAGRAMS.md - available in [GitHub Actions artifacts](../../actions/workflows/generate-diagrams-pdf.yml)

## Quick Start

### Using Pre-built Multi-architecture Images

Pre-built Docker images are available on GitHub Container Registry (GHCR) supporting multiple architectures:
- **amd64** (x86_64)
- **armv7** (32-bit ARM)
- **aarch64** (64-bit ARM)

```bash
# Pull the latest images
docker pull ghcr.io/chester929/multizone-logic:latest
docker pull ghcr.io/chester929/multizone-frontend:latest
docker pull ghcr.io/chester929/multizone-mqtt:latest

# Or use specific versions
docker pull ghcr.io/chester929/multizone-logic:v1.0.0
```

The images will automatically select the correct architecture for your platform.

### Using Docker Compose (Local Development)

```bash
# Clone the repository
git clone https://github.com/Chester929/ha_multizone_climate.git
cd ha_multizone_climate

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the services
make start
# Or: docker-compose up -d

# Access the frontend
# Open http://localhost:8099 in your browser
```

### As a Home Assistant Add-on

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure and start the add-on
4. Access through the sidebar or Web UI button

For detailed instructions, see [IMPLEMENTATION.md](IMPLEMENTATION.md).

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
│  │  • HA API Client │  │  • MQTT Settings │  │              │ │
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
│           │                     │                    │         │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌──────▼──────┐ │
│  │  MQTT Middleware │  │  HA API Client   │  │ Auto-Install│ │
│  │   (Optional)     │  │   (Optional)     │  │ Integration │ │
│  │                  │  │                  │  │ (Optional)  │ │
│  │  Redis ←→ MQTT   │  │  Redis ←→ HA API │  └─────────────┘ │
│  └────────┬─────────┘  └────────┬─────────┘                  │
│           │                     │                             │
└───────────┼─────────────────────┼─────────────────────────────┘
            │                     │
            │ MQTT over TCP       │ REST API + WebSocket
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Home Assistant                             │
│                                                                 │
│  Via MQTT (creates new entities):                              │
│  • Climate Entities (zones + main)                             │
│  • Sensor Entities (temperatures, states)                      │
│  • Binary Sensor Entities (valve states)                       │
│  • Switch Entities (zone enable/disable)                       │
│                                                                 │
│  Via Service API (uses existing entities):                     │
│  • Existing temperature sensors (read via state API)           │
│  • Existing switch entities (control via service calls)        │
│  • Existing climate entity (main thermostat)                   │
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
- Publishes events to MQTT (if MQTT enabled)
- Calls Home Assistant REST API and WebSocket (if HA API enabled)
- Uses existing HA entities (sensors, switches) for control

#### 2. Frontend WebApp (TypeScript)
**Purpose:** User interface for management and monitoring

**Responsibilities:**
- Zone management (add, edit, delete zones)
- Thermostat configuration
- Real-time statistics and metrics
- Configuration interface for MQTT integration
- Configuration interface for HA Service API integration
- Entity mapping (existing HA entities to zones)
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
- Manages HA Service API settings
- Configures entity ID mappings

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

#### 5. Home Assistant Service API Integration (Optional)
**Purpose:** Direct integration using Home Assistant's REST API and WebSocket

**Functionality:**
- Logic container connects directly to Home Assistant API
- Uses existing HA entities (sensors, switches) - no new entities created
- Calls HA services to control valves and read sensors
- Bidirectional real-time updates via WebSocket
- No MQTT broker required

**Enabled when:** User configures HA API integration in frontend

**Uses Existing HA Entities:**
- Reads from existing temperature sensor entities
- Controls existing switch entities (valves)
- Monitors existing climate entity (main thermostat)
- No discovery needed - user maps existing entities in configuration

**Configuration:**
- Home Assistant URL and access token
- Entity ID mapping (zone name → sensor/switch entity IDs)
- Polling interval and WebSocket settings

**Benefits:**
- No additional infrastructure (MQTT broker)
- Uses entities already configured in HA
- Direct service calls for instant control
- Real-time state updates via WebSocket

#### 6. Auto-Install Integration (Python)
**Purpose:** Optional HA custom integration for advanced users

**Alternative to Service API/MQTT:**
- Direct Python integration installed automatically
- Runs inside Home Assistant core
- Communicates with Logic container via HTTP API or Redis
- Provides same entities as MQTT approach
- For users who prefer native integration over external API calls

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

1. Deploy containers separately using pre-built multi-architecture images from GHCR:
   ```bash
   docker pull ghcr.io/chester929/multizone-logic:latest
   docker pull ghcr.io/chester929/multizone-frontend:latest
   docker pull ghcr.io/chester929/multizone-mqtt:latest
   ```
   - Supports amd64, armv7, and aarch64 architectures
   - Or use specific version tags (e.g., `v1.0.0`)
   - Add external Redis if needed: `docker pull redis:7-alpine`
2. Configure via environment variables or config files
3. Connect to MQTT broker or install custom integration

## Integration Options

The add-on offers **three flexible integration methods** with Home Assistant:

### Option 1: Home Assistant Service API (Recommended for most users)
**Best for:** Users who want to use their existing HA entities without MQTT infrastructure

**How it works:**
- Logic container connects directly to Home Assistant's REST API and WebSocket
- Uses your existing temperature sensor and switch entities
- No new entities created in HA
- Real-time bidirectional communication
- No MQTT broker required

**Configuration:**
- Provide HA URL and long-lived access token
- Map existing entity IDs to zones in the frontend UI
- Example: Zone "Bedroom" → `sensor.bedroom_temperature` + `switch.bedroom_valve`

**Pros:**
- ✅ Simple setup - no MQTT broker needed
- ✅ Uses entities you already have
- ✅ Direct service calls for instant control
- ✅ Real-time state updates via WebSocket

**Cons:**
- ⚠️ Requires access token management
- ⚠️ Slightly higher latency than Python integration

### Option 2: MQTT Integration (zigbee2mqtt style)
**Best for:** Users familiar with MQTT or running other MQTT-based integrations

**How it works:**
- MQTT middleware bridges Redis state to MQTT topics
- Auto-discovers and creates new entities in Home Assistant
- Uses `homeassistant/` discovery prefix
- Bidirectional MQTT communication

**Configuration:**
- Configure MQTT broker connection in frontend
- Entities automatically appear in HA
- Example: `climate.multizone_bedroom`, `sensor.multizone_bedroom_temperature`

**Pros:**
- ✅ Standardized MQTT pattern (like zigbee2mqtt)
- ✅ Auto-discovery - no manual entity creation
- ✅ Works with existing MQTT infrastructure
- ✅ Event-driven architecture

**Cons:**
- ⚠️ Requires MQTT broker (Mosquitto, etc.)
- ⚠️ Creates new entities (not using existing ones)

### Option 3: Python Custom Integration
**Best for:** Advanced users who want native HA integration

**How it works:**
- Python integration installed automatically by add-on
- Runs inside Home Assistant core
- Communicates with Logic container via HTTP API or Redis
- Creates native HA entities

**Configuration:**
- Auto-installed by add-on
- Configured through HA integration UI
- Provides same functionality as other methods

**Pros:**
- ✅ Native Home Assistant integration
- ✅ No external dependencies
- ✅ Tight integration with HA core

**Cons:**
- ⚠️ More complex to debug
- ⚠️ Creates new entities (not using existing ones)

### Comparison Table

| Feature | HA Service API | MQTT | Python Integration |
|---------|---------------|------|-------------------|
| Uses existing HA entities | ✅ Yes | ❌ Creates new | ❌ Creates new |
| Requires MQTT broker | ❌ No | ✅ Yes | ❌ No |
| Setup complexity | ⭐⭐ Medium | ⭐⭐⭐ Higher | ⭐ Simple |
| Real-time updates | ✅ WebSocket | ✅ MQTT | ✅ Native |
| External dependencies | Access token | MQTT broker | None |
| Integration style | API calls | Event-driven | Native |

**Recommendation:** Start with **Home Assistant Service API** if you have existing sensors and switches configured in HA. Switch to **MQTT** if you want auto-discovery or already use MQTT. Use **Python Integration** for the most native experience.

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

- **Integration:** Multiple options
  - MQTT: Industry standard, widely supported
  - HA Service API: Direct integration with existing entities
  - Python: Native Home Assistant custom integration
  - User choice based on preference and setup

## Configuration Example

### Add-on Configuration
```yaml
redis:
  mode: bundled  # or 'external'
  host: localhost  # if external
  port: 6379
  password: ""
  
mqtt:
  enabled: false  # Enable MQTT integration
  broker: homeassistant.local
  port: 1883
  username: mqtt_user
  password: mqtt_pass
  discovery_prefix: homeassistant
  topic_prefix: multizone

homeassistant_api:
  enabled: true  # Enable HA Service API integration
  url: http://homeassistant.local:8123
  access_token: "your_long_lived_access_token"
  websocket_enabled: true
  polling_interval: 5  # seconds

logic:
  coordinator_interval: 15  # seconds
  valve_actuation_delay: 120  # seconds
  main_change_threshold: 0.5  # °C
  
frontend:
  port: 8099
  auth: basic  # or 'none'
  
custom_integration:
  auto_install: false  # Not needed when using MQTT or HA API
```

### Frontend Configuration
- Access web interface at `http://homeassistant.local:8099`
- **Zone Configuration:**
  - Zone name and settings
  - Map existing HA entities to zones:
    - Temperature sensor entity ID (e.g., `sensor.bedroom_temperature`)
    - Valve switch entity ID (e.g., `switch.bedroom_valve`)
  - Or create new entities via MQTT (if MQTT enabled)
  - Set temperature offsets and thresholds
- **Main Climate:**
  - Select existing main climate entity (e.g., `climate.main_thermostat`)
  - Configure calculation parameters
- **Integration Settings:**
  - Choose integration method (MQTT, HA Service API, or Python)
  - Configure MQTT broker (if MQTT selected)
  - Configure HA API connection (if Service API selected)
  - Test connection and validate entity access
- **Statistics & Metrics:**
  - View real-time temperature graphs
  - Monitor valve activity
  - Historical data analysis

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
- [ ] Home Assistant entity discovery (MQTT)
- [ ] Bidirectional MQTT communication
- [ ] Home Assistant Service API client
- [ ] WebSocket connection for real-time updates
- [ ] Entity ID mapping and validation
- [ ] Auto-install custom integration (alternative to MQTT/API)

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
- [x] Multi-architecture builds
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
