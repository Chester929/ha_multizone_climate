# ha_multizone_climate

Home Assistant Add-on for advanced multi-zone HVAC management.

## Overview

This project provides a Home Assistant add-on for managing multiple heating/cooling zones in your setup. The system intelligently coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency.

## Documentation

- **[DIAGRAMS.md](DIAGRAMS.md)**: System architecture and diagrams
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Implementation guide and deployment instructions
- **[DOCKER_BUILDS.md](DOCKER_BUILDS.md)**: Multi-architecture Docker builds documentation
- **[VALVE_MANAGEMENT.md](VALVE_MANAGEMENT.md)**: Valve control and safety features
- **[STATISTICS_API.md](STATISTICS_API.md)**: Statistics and metrics API documentation

## Quick Start

### Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure the addon options in the Configuration tab
4. Start the add-on
5. Access the UI through the Home Assistant sidebar (Multizone Climate panel) or via the Web UI button in the add-on page

## The Problem

I have an HVAC unit driven by one thermostat using a heating curve to calculate the correct temperature in pipes. I would like to manage temperature per room using sensors and valve controllers. The HVAC is missing a circulating line, so there has to be at least one valve still open.

### Main Climate Unit and Thermostat

- HVAC unit controlled by one thermostat through physical cables
- Thermostat placed in corridor with its own temperature sensor
- Uses heating curve to calculate water temperature based on outdoor temperature
- Existing custom component: https://github.com/Chester929/remeha_home_by_chester
- Controls: target temperature and HVAC mode (OFF/Anti-Freeze, Manual, Scheduler)

### Heat Zones

- Temperature sensors in rooms integrated with Home Assistant
- Heat pipe valves (open/close) for each room controlled remotely via switch entities
- Need intelligent coordination to prevent all valves from closing (safety requirement)

## Architecture - Addon-Only Solution

This project is a Home Assistant add-on with a containerized microservices architecture:

\`\`\`
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant Add-on                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  Logic Container │  │ Frontend WebApp  │  │    Redis     │ │
│  │    (GoLang)      │  │  (TypeScript)    │  │  (Bundled)   │ │
│  │                  │  │                  │  │              │ │
│  │  • Core Logic    │  │  • Zone Mgmt     │  │  • State     │ │
│  │  • Algorithms    │  │  • Statistics    │  │  • Config    │ │
│  │  • Valve Control │  │  • Metrics       │  │  • Queues    │ │
│  │  • Safety Checks │  │  • Configuration │  │              │ │
│  │  • REST API      │  │  • Web Interface │  │              │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           │                     │                    │         │
│           └─────────────────────┴────────────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                    HA Addon Ingress (Web UI)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Home Assistant                             │
│                                                                 │
│  Users reference existing entities manually:                   │
│  • Temperature sensors (e.g., sensor.bedroom_temp)             │
│  • Switch entities for valves (e.g., switch.bedroom_valve)     │
│  • Main climate entity (e.g., climate.main_thermostat)         │
│                                                                 │
│  Add-on accessed through HA Ingress (sidebar panel)            │
└─────────────────────────────────────────────────────────────────┘
\`\`\`

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
- REST API for frontend communication

**Technology:** GoLang for performance, concurrency, and low resource usage

**Communication:**
- Reads/writes state to Redis
- Provides REST API for frontend

#### 2. Frontend WebApp (TypeScript)
**Purpose:** User interface for management and monitoring

**Responsibilities:**
- Zone management (add, edit, delete zones)
- Thermostat configuration
- Real-time statistics and metrics
- Entity ID entry (users manually enter entity IDs)
- Visual dashboards for monitoring
- Historical data visualization

**Technology:** TypeScript with modern web framework

**Features:**
- Responsive design
- Real-time updates
- Interactive charts and graphs
- Mobile-friendly interface

**Communication:**
- Reads/writes configuration to Redis via backend API
- Displays real-time data from backend

#### 3. Redis Container (Bundled)
**Purpose:** Data persistence and message queuing

**Stores:**
- Global configuration
- Zone states and configurations
- Job queues (calculate temp, update valves, safety check)
- Valve locks and timestamps
- Historical metrics

## Installation

### As a Home Assistant Add-on (Recommended)

1. Add this repository to your Home Assistant add-on store:
   - Go to Supervisor → Add-on Store → ⋮ (menu) → Repositories
   - Add: \`https://github.com/Chester929/ha_multizone_climate\`
   
2. Install the "Multizone Climate" add-on from the add-on store

3. Configure the add-on options:
   \`\`\`yaml
   redis:
     mode: bundled  # or 'external' if you have your own Redis server
     password: ""   # set a password if using external Redis
   
   logic:
     log_level: "info"  # debug, info, warning, or error
   
   frontend:
     port: 8099
   \`\`\`

4. Start the add-on

5. Access the UI:
   - Via Home Assistant sidebar: Click "Multizone Climate" panel
   - Via add-on page: Click "OPEN WEB UI" button
   - Direct access: \`http://homeassistant.local:8099\` (if ports exposed)

## Configuration

### Add-on Configuration

Configure the add-on through the Home Assistant UI:

- **Redis Mode**: Use bundled Redis or connect to external server
- **Log Level**: Set verbosity (debug, info, warning, error)
- **Frontend Port**: Web interface port (default: 8099)

### Zone Configuration

Access the web interface to configure zones:

1. **Create Zones**: 
   - Click "Add Zone" button
   - Enter zone name
   - Manually enter entity IDs for:
     - Temperature sensor (e.g., \`sensor.bedroom_temperature\`)
     - Valve switch (e.g., \`switch.bedroom_valve\`)
     - Climate entity (optional, e.g., \`climate.bedroom_thermostat\`)
   - Set target temperature and priority

2. **Configure Main Climate**:
   - Go to Configuration tab
   - Set main climate entity ID
   - Configure calculation parameters
   - Set safety thresholds

3. **Monitor Statistics**:
   - View real-time temperature graphs
   - Monitor valve activity
   - Analyze historical data

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
- Real-time statistics and metrics
- Historical data tracking

## Technology Stack

- **Backend Logic:** GoLang
  - High performance
  - Excellent concurrency (goroutines)
  - Low memory footprint
  - Strong typing
  
- **Frontend:** TypeScript
  - Type safety
  - Modern React framework
  - Real-time updates
  - Responsive design

- **State Management:** Redis
  - Fast in-memory storage
  - Persistence options
  - Simple and reliable

- **Integration:** Home Assistant Add-on
  - Native HA ingress support
  - Sidebar panel integration
  - Addon supervisor integration

## Hardware Requirements

- Home Assistant OS/Supervised installation (for add-on)
- Minimum 512MB RAM (1GB recommended)
- Supported architectures: amd64, armv7, aarch64
- Temperature sensors integrated with Home Assistant
- Switch entities for valve control
- Main climate entity for HVAC control

## Development Roadmap

### Phase 1: Foundation ✅
- [x] GoLang logic container with core algorithms
- [x] Redis integration and state management
- [x] Basic job processing and queue system
- [x] Safety checks and valve management

### Phase 2: Frontend ✅
- [x] TypeScript web application
- [x] Zone management UI
- [x] Configuration interface
- [x] Real-time monitoring dashboard

### Phase 3: Add-on Integration ✅
- [x] Home Assistant add-on packaging
- [x] Ingress support for web UI
- [x] Panel icon and sidebar integration
- [x] Multi-architecture Docker builds

### Phase 4: Enhancement 🚧
- [ ] Statistics and historical data improvements
- [ ] Advanced metrics and analytics
- [ ] Additional language translations
- [ ] Performance optimization

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## License

MIT License - See LICENSE file for details

## Support

- **Issues:** https://github.com/Chester929/ha_multizone_climate/issues
- **Documentation:** See README.md and other .md files
- **Community:** Home Assistant Community Forum

## Related Projects

- [remeha_home_by_chester](https://github.com/Chester929/remeha_home_by_chester) - Main climate thermostat custom component

## Frequently Asked Questions

### How do I reference my Home Assistant entities?

Simply enter the entity IDs manually in the zone configuration. For example:
- Temperature sensor: \`sensor.bedroom_temperature\`
- Valve switch: \`switch.bedroom_valve\`
- Climate entity: \`climate.bedroom_thermostat\`

### Does this create new entities in Home Assistant?

No, this add-on does not create any new entities. It's a standalone zone management system that references your existing Home Assistant entities through their entity IDs.

### How does the add-on communicate with Home Assistant?

The add-on runs as a native Home Assistant add-on and is accessed through HA's ingress system (sidebar panel). It doesn't directly communicate with HA entities - users manually reference entity IDs in the configuration.

### Can I use this with any HVAC system?

Yes, as long as you have:
- Temperature sensors in Home Assistant
- Switch entities to control valves
- A main climate entity for the HVAC system

### What if all valves want to close?

The system has built-in safety features that ensure at least one valve stays open (configurable minimum). This prevents damage to HVAC systems that require circulation.
