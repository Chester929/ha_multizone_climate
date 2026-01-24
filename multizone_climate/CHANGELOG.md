# Changelog

All notable changes to the Multizone Climate add-on will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-24

### Added

#### Core Features
- **2-Container Add-on Architecture**
  - Logic container (GoLang) for core algorithms and REST API
  - Redis container for state storage and job queuing
  - Automatic custom integration installation to `/config/custom_components/`

- **Native Python Custom Integration**
  - Config flow with entity selectors for easy zone setup
  - Climate entities created for each configured zone
  - Coordinator pattern for polling backend commands
  - Event-driven temperature synchronization

- **Intelligent Zone Management**
  - Per-zone temperature control with configurable targets
  - Priority-based zone satisfaction (0-100 scale)
  - Zone state machine (satisfied, cooling, warming)
  - Enable/disable zones individually

- **Valve Control System**
  - Automatic valve open/close based on zone demand
  - Valve actuation delay to prevent mechanical wear
  - Valve lock mechanism with expiration tracking
  - Chattering prevention with hysteresis
  - Open-first-then-close sequencing for safety

- **Safety Features**
  - Minimum valves open enforcement (configurable)
  - Fallback valve activation when all zones satisfied
  - Error recovery and graceful degradation
  - Valve lock mechanism during maintenance

- **Main Climate Optimization**
  - Automatic calculation of optimal main thermostat temperature
  - Multiple calculation modes (slider-based, average unsatisfied)
  - Precision control (0.5°C for main climate, 0.1°C for zones)
  - Overheated zone exclusion from calculations

- **REST API**
  - Health check endpoint
  - Zone management (list, create, update, delete)
  - Command polling for integration
  - State synchronization from integration
  - Global configuration management
  - Statistics and metrics endpoints

- **Statistics and Metrics**
  - Temperature history tracking (up to 30 days)
  - Valve activity logging
  - Energy consumption estimates
  - Comfort metrics per zone
  - System performance metrics

#### Configuration
- **Add-on Options**
  - Configurable coordinator polling interval (5-300 seconds)
  - Configurable backend API port (1024-65535)
  - Redis mode selection (bundled or external)
  - External Redis connection support
  - Redis password authentication
  - Log level control (debug, info, warning, error)

#### Architecture
- **Multi-Architecture Support**
  - amd64 (x86_64)
  - armv7 (32-bit ARM)
  - aarch64 (64-bit ARM)

- **Docker Images**
  - Base images from Home Assistant official repository
  - Optimized image sizes
  - Health checks and automatic restarts

#### Documentation
- Comprehensive README with quick start guide
- Detailed DOCS.md with configuration reference
- DIAGRAMS.md with architecture and algorithm visualizations
- API documentation
- Troubleshooting guide
- Local development setup instructions

#### Testing
- 47 passing unit tests for Go algorithms
- Integration tests for add-on services
- Test coverage for temperature precision
- Valve management algorithm tests
- API endpoint tests

#### Developer Experience
- Makefile with common development commands
- Docker Compose for local development
- Example configuration files
- Go module structure
- Python type hints and formatting
- CI/CD workflows with GitHub Actions

### Technical Details

- **Languages**: GoLang (backend), Python 3.11+ (integration)
- **Database**: Redis (in-memory with persistence)
- **API**: RESTful HTTP on port 8080
- **Home Assistant**: Requires OS or Supervised installation
- **Minimum HA Version**: 2024.1.0

### Known Limitations

- No web UI for add-on configuration (uses standard add-on config)
- Requires manual zone configuration through integration
- AppArmor profile not included (planned for future release)
- Single language support (English only in v0.1.0)

### Dependencies

- **Go Packages**
  - github.com/go-redis/redis/v8
  - github.com/gorilla/mux
  - Standard library

- **Python Packages** (Custom Integration)
  - homeassistant >= 2024.1.0
  - aiohttp
  - voluptuous

- **System**
  - Docker
  - Home Assistant Supervisor
  - Minimum 512MB RAM (1GB recommended)

---

## [Unreleased]

### Planned Features

- AppArmor security profile
- Multi-language support (Czech, Slovak, Polish)
- Enhanced statistics dashboard
- Zone groups and profiles
- Scheduling and automation templates
- Advanced valve control modes
- Energy cost tracking
- Weather integration
- Learning algorithms for optimal scheduling

---

[0.1.0]: https://github.com/Chester929/ha_multizone_climate/releases/tag/v0.1.0
