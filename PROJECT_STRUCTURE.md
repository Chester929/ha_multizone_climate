# Home Assistant Multizone Climate - Project Structure

## Executive Summary

This document defines the complete project structure for the **Home Assistant Multizone Climate** integration. After careful analysis, this project should be implemented as:

1. **Primary Component**: A **custom Home Assistant integration** installable via HACS
2. **Frontend Component**: Custom Lovelace cards packaged within the integration
3. **External Dependency**: Redis (managed separately by user or Home Assistant add-on)

**Rationale**: A custom integration provides the best balance of:
- Easy installation via HACS
- Full Home Assistant API access
- Native entity integration
- Custom frontend components
- No supervisor dependency (works on all HA installations)

---

## Table of Contents

1. [Architecture Decision](#architecture-decision)
2. [Directory Structure](#directory-structure)
3. [Component Details](#component-details)
4. [Frontend Structure](#frontend-structure)
5. [Development Workflow](#development-workflow)
6. [Installation & Deployment](#installation--deployment)
7. [Testing Strategy](#testing-strategy)
8. [HACS Compatibility](#hacs-compatibility)
9. [Dependencies](#dependencies)

---

## Architecture Decision

### Why Custom Integration (Not Add-on)?

| Aspect | Custom Integration ✅ | Home Assistant Add-on ❌ |
|--------|----------------------|-------------------------|
| **Installation** | Via HACS (simple) | Requires Supervisor |
| **Compatibility** | All HA installations | Supervisor only (no Docker, no Core) |
| **Entity Integration** | Native | Requires MQTT/API bridge |
| **Frontend** | Integrated cards | Separate web UI |
| **Updates** | Via HACS | Via Supervisor |
| **Development** | Python-based | Container-based |

**Conclusion**: Custom integration is the clear choice for this project.

### Redis Dependency

Redis will be an **external dependency** that users must provide:
- **Option 1**: Use existing Home Assistant Redis add-on (for Supervisor users)
- **Option 2**: Use external Redis server (for Docker/Core users)
- **Option 3**: Future consideration: bundled lightweight Redis alternative

This keeps the integration lightweight and flexible.

---

## Directory Structure

```
ha_multizone_climate/
├── .github/                                 # GitHub configurations
│   ├── workflows/
│   │   ├── generate-diagrams-pdf.yml       # Diagram PDF generation
│   │   ├── tests.yml                        # CI/CD: Run tests
│   │   ├── lint.yml                         # CI/CD: Code quality checks
│   │   └── release.yml                      # CI/CD: HACS release automation
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   └── WORKFLOW_TESTING.md
│
├── custom_components/                       # Home Assistant integration
│   └── multizone_climate/                   # Integration package name
│       ├── __init__.py                      # Integration setup & config entry
│       ├── manifest.json                    # Integration metadata (REQUIRED)
│       ├── config_flow.py                   # Configuration UI flow
│       ├── const.py                         # Constants and defaults
│       ├── coordinator.py                   # Data update coordinator (15s cycle)
│       ├── device.py                        # Main climate device
│       ├── entity.py                        # Base entity class
│       │
│       ├── core/                            # Core logic modules
│       │   ├── __init__.py
│       │   ├── redis_client.py              # Redis connection & operations
│       │   ├── algorithms.py                # Core algorithms (calc temp, update valves)
│       │   ├── satisfaction.py              # Satisfaction state machine logic
│       │   ├── valve_control.py             # Valve management & locking
│       │   └── safety.py                    # Safety checks & fallback logic
│       │
│       ├── jobs/                            # Background job implementations
│       │   ├── __init__.py
│       │   ├── base.py                      # Base job class with locking
│       │   ├── calculate_main_temp.py       # Calculate main target temperature job
│       │   ├── update_valves.py             # Update valves job
│       │   └── safety_check.py              # Safety valve check job
│       │
│       ├── platforms/                       # Home Assistant platforms
│       │   ├── climate.py                   # Climate entities (main + zones)
│       │   ├── sensor.py                    # Sensor entities (states, metrics)
│       │   ├── switch.py                    # Switch entities (multizone enable)
│       │   └── binary_sensor.py             # Binary sensors (status indicators)
│       │
│       ├── services/                        # Custom services
│       │   ├── __init__.py
│       │   └── services.yaml                # Service definitions
│       │
│       ├── automations/                     # Automation triggers
│       │   ├── __init__.py
│       │   ├── temperature_change.py        # Temperature/target change automation
│       │   └── safety_timer.py              # Safety check timer
│       │
│       ├── translations/                    # Internationalization
│       │   ├── en.json                      # English (default)
│       │   ├── cs.json                      # Czech
│       │   ├── sk.json                      # Slovak
│       │   └── pl.json                      # Polish
│       │
│       ├── www/                             # Frontend resources (served by HA)
│       │   ├── multizone-climate-card.js    # Zone climate card (bundled)
│       │   ├── multizone-main-card.js       # Main climate card (bundled)
│       │   ├── multizone-dashboard.js       # Dashboard panel (bundled)
│       │   └── icons/                       # Custom icons
│       │
│       └── strings.json                     # UI strings (config flow, etc.)
│
├── frontend/                                # Frontend source code (not deployed)
│   ├── src/
│   │   ├── cards/
│   │   │   ├── multizone-climate-card.ts    # Zone climate card (TypeScript)
│   │   │   ├── multizone-main-card.ts       # Main climate card (TypeScript)
│   │   │   └── multizone-dashboard.ts       # Dashboard panel (TypeScript)
│   │   ├── components/                      # Shared UI components
│   │   │   ├── zone-temperature-display.ts
│   │   │   ├── valve-status-indicator.ts
│   │   │   ├── satisfaction-badge.ts
│   │   │   └── config-editor.ts
│   │   ├── styles/                          # Shared styles
│   │   │   └── common.css
│   │   └── utils/                           # Utility functions
│   │       ├── format.ts
│   │       └── ha-helpers.ts
│   ├── package.json                         # Frontend dependencies
│   ├── tsconfig.json                        # TypeScript configuration
│   ├── rollup.config.js                     # Build configuration (bundle to www/)
│   └── .eslintrc.js                         # Linting configuration
│
├── tests/                                   # Test suite
│   ├── __init__.py
│   ├── conftest.py                          # Pytest fixtures & config
│   ├── fixtures/                            # Test data & fixtures
│   │   ├── config.json
│   │   ├── zones.json
│   │   └── redis_mock_data.json
│   │
│   ├── unit/                                # Unit tests
│   │   ├── test_algorithms.py               # Core algorithm tests
│   │   ├── test_satisfaction.py             # Satisfaction state machine tests
│   │   ├── test_valve_control.py            # Valve control logic tests
│   │   ├── test_safety.py                   # Safety check tests
│   │   ├── test_redis_client.py             # Redis client tests
│   │   └── test_jobs.py                     # Background job tests
│   │
│   ├── integration/                         # Integration tests
│   │   ├── test_config_flow.py              # Configuration flow tests
│   │   ├── test_coordinator.py              # Coordinator tests
│   │   ├── test_climate_platform.py         # Climate entity tests
│   │   ├── test_sensor_platform.py          # Sensor entity tests
│   │   ├── test_automation.py               # Automation trigger tests
│   │   └── test_job_queueing.py             # Job queue tests
│   │
│   └── scenarios/                           # Scenario-based tests
│       ├── test_temperature_drop.py         # Scenario 1: Zone temp drop
│       ├── test_valve_swapping.py           # Scenario 2: Valve swap at minimum
│       ├── test_multiple_changes.py         # Scenario 3: Multiple rapid changes
│       ├── test_cooling_mode.py             # Scenario 4: Cooling mode
│       └── test_multizone_toggle.py         # Scenario 5: Enable/disable multizone
│
├── docs/                                    # Documentation
│   ├── installation.md                      # Installation guide
│   ├── configuration.md                     # Configuration guide
│   ├── user-guide.md                        # User guide
│   ├── troubleshooting.md                   # Troubleshooting
│   ├── api.md                               # API documentation
│   ├── development.md                       # Development guide
│   ├── screenshots/                         # UI screenshots
│   └── examples/                            # Configuration examples
│       ├── basic-setup.yaml
│       ├── advanced-setup.yaml
│       └── redis-config-examples.md
│
├── scripts/                                 # Development scripts
│   ├── setup_dev.sh                         # Setup development environment
│   ├── run_tests.sh                         # Run all tests
│   ├── build_frontend.sh                    # Build frontend assets
│   ├── validate_hacs.sh                     # Validate HACS compatibility
│   └── release.sh                           # Create release
│
├── .devcontainer/                           # VS Code devcontainer (optional)
│   ├── devcontainer.json
│   └── Dockerfile
│
├── .vscode/                                 # VS Code configuration
│   ├── settings.json
│   ├── launch.json
│   └── extensions.json
│
├── hacs.json                                # HACS metadata (REQUIRED)
├── info.md                                  # HACS info page (REQUIRED)
├── README.md                                # Project readme
├── DIAGRAMS.md                              # System diagrams
├── PROJECT_STRUCTURE.md                     # This file
├── LICENSE                                  # License file
├── CHANGELOG.md                             # Version history
│
├── .gitignore                               # Git ignore rules
├── .pylintrc                                # Pylint configuration
├── .flake8                                  # Flake8 configuration
├── pyproject.toml                           # Python project metadata
├── requirements.txt                         # Python dependencies
├── requirements_dev.txt                     # Development dependencies
└── setup.py                                 # Python package setup (optional)
```

---

## Component Details

### 1. Integration Core (`custom_components/multizone_climate/`)

#### `manifest.json` (REQUIRED)
Defines integration metadata for Home Assistant:

```json
{
  "domain": "multizone_climate",
  "name": "Multizone Climate",
  "version": "1.0.0",
  "documentation": "https://github.com/Chester929/ha_multizone_climate",
  "issue_tracker": "https://github.com/Chester929/ha_multizone_climate/issues",
  "dependencies": [],
  "codeowners": ["@Chester929"],
  "requirements": [
    "redis>=4.5.0",
    "aioredis>=2.0.0"
  ],
  "config_flow": true,
  "iot_class": "local_polling",
  "integration_type": "device"
}
```

#### `__init__.py`
- Integration setup and teardown
- Config entry management
- Platform loading (climate, sensor, switch, binary_sensor)
- Service registration
- Coordinator initialization

#### `config_flow.py`
- Configuration UI flow
- Redis connection validation
- Main climate entity selection
- Configuration options (sliders, checkboxes)
- Zone management UI

#### `coordinator.py`
- `DataUpdateCoordinator` subclass
- Runs every 15 seconds
- Fetches data from Redis
- Updates sensor states
- Dequeues and executes jobs

### 2. Core Logic (`core/`)

#### `redis_client.py`
- Redis connection management
- Key pattern definitions
- CRUD operations for config, zones, queues, locks
- Connection pooling
- Error handling and reconnection logic

#### `algorithms.py`
- `calculate_main_target_temperature()` - Slider-based and average modes
- Main target calculation logic
- Temperature rounding and clamping

#### `satisfaction.py`
- Zone satisfaction state machine
- Heating mode state transitions
- Cooling mode state transitions
- Hysteresis logic with satisfaction_eps

#### `valve_control.py`
- Valve priority sorting
- Open-first-then-close logic
- Valve lock management
- Minimum valves enforcement

#### `safety.py`
- Safety valve check
- Fallback valve selection
- Minimum valves enforcement

### 3. Background Jobs (`jobs/`)

#### `base.py`
- Base job class with Redis job locking
- Job status tracking
- Error handling and retry logic

#### `calculate_main_temp.py`
- Implements calculate main target temperature job
- Reads zones from Redis
- Calls core algorithm
- Updates main climate entity

#### `update_valves.py`
- Implements update valves job
- Reads zone satisfaction states
- Calls valve control logic
- Executes valve open/close commands

#### `safety_check.py`
- Implements safety valve check job
- Checks minimum valves open
- Forces open fallback valves if needed

### 4. Platforms (`platforms/`)

#### `climate.py`
- Main climate device (represents integration)
- Zone climate entities (one per zone)
- Temperature control
- HVAC mode management
- Satisfaction state display

#### `sensor.py`
- Temperature sensors (current, target, outdoor)
- Satisfaction state sensors
- Valve state sensors
- Job status sensors
- Diagnostic sensors

#### `switch.py`
- Multizone enable/disable switch
- Per-zone enable/disable switches

#### `binary_sensor.py`
- System status indicators
- Error/warning indicators
- Redis connection status

### 5. Automations (`automations/`)

#### `temperature_change.py`
- Listens for temperature sensor state changes
- Listens for zone target temperature changes
- Debounces events (~5 seconds)
- Enqueues calculate_main_temp and update_valves jobs

#### `safety_timer.py`
- Timer-based trigger (valve_actuation_delay / 2)
- Directly executes safety_valve_check job

---

## Frontend Structure

### Custom Lovelace Cards

All frontend code is written in **TypeScript** using **Lit** (Home Assistant's web component framework) and bundled to JavaScript for deployment.

#### 1. Zone Climate Card (`multizone-climate-card`)
- Displays zone name, current temp, target temp
- Temperature adjustment controls (+/-)
- Satisfaction status badge (underheated/satisfied/overheated)
- Valve state indicator (open/closed/opening/closing)
- Temperature direction indicator (rising/falling)
- Zone priority and fallback status
- Configurable card options

#### 2. Main Climate Card (`multizone-main-card`)
- Displays main climate entity
- Current and target temperature
- Outdoor temperature
- HVAC mode and action
- Multizone enable/disable toggle
- All zones summary (count satisfied/underheated/overheated)
- Visual status indicators

#### 3. Dashboard Panel (`multizone-dashboard`)
- Full-page monitoring dashboard
- Grid of all zone cards
- Main climate card
- Real-time metrics:
  - Open valves count
  - Job queue status
  - Recent actions log
  - System health indicators
- Configuration editor (optional)

### Frontend Build Process

```bash
cd frontend/
npm install
npm run build  # Bundles TypeScript to JavaScript in custom_components/multizone_climate/www/
```

### Frontend Dependencies

```json
{
  "devDependencies": {
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "eslint": "^8.0.0",
    "rollup": "^3.0.0",
    "rollup-plugin-typescript2": "^0.36.0",
    "typescript": "^5.0.0"
  },
  "dependencies": {
    "lit": "^3.0.0",
    "home-assistant-js-websocket": "^9.0.0"
  }
}
```

---

## Development Workflow

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/Chester929/ha_multizone_climate.git
cd ha_multizone_climate

# Install Python dependencies
pip install -r requirements_dev.txt

# Install pre-commit hooks (optional)
pre-commit install

# Setup Redis for testing (Docker)
docker run -d -p 6379:6379 redis:latest

# Build frontend
cd frontend/
npm install
npm run build
cd ..
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_algorithms.py

# Run with coverage
pytest --cov=custom_components.multizone_climate --cov-report=html

# Run integration tests only
pytest tests/integration/
```

### Code Quality Checks

```bash
# Lint Python code
pylint custom_components/multizone_climate/

# Format Python code
black custom_components/multizone_climate/

# Type checking
mypy custom_components/multizone_climate/

# Lint frontend code
cd frontend/
npm run lint
npm run format
```

### Building Frontend

```bash
cd frontend/
npm run build  # Production build
npm run dev    # Development build with watching
```

### Testing in Home Assistant

1. Copy `custom_components/multizone_climate/` to your HA config directory:
   ```
   ~/.homeassistant/custom_components/multizone_climate/
   ```

2. Restart Home Assistant

3. Add integration via UI: Configuration → Integrations → Add Integration → "Multizone Climate"

---

## Installation & Deployment

### For Users (HACS)

1. **Install HACS** (if not already installed)
   - Follow: https://hacs.xyz/docs/setup/download

2. **Add Custom Repository**
   - HACS → Integrations → 3-dot menu → Custom repositories
   - URL: `https://github.com/Chester929/ha_multizone_climate`
   - Category: Integration

3. **Install Integration**
   - HACS → Integrations → Search "Multizone Climate"
   - Click "Download"

4. **Setup Redis** (if not already running)
   - **Supervisor users**: Install "Redis" add-on from Add-on Store
   - **Docker/Core users**: Run external Redis server

5. **Configure Integration**
   - Configuration → Integrations → Add Integration → "Multizone Climate"
   - Follow configuration flow

### For Developers (Manual)

```bash
# Clone repository
git clone https://github.com/Chester929/ha_multizone_climate.git

# Build frontend
cd ha_multizone_climate/frontend/
npm install
npm run build

# Copy to Home Assistant
cp -r ../custom_components/multizone_climate ~/.homeassistant/custom_components/

# Restart Home Assistant
```

---

## Testing Strategy

### Unit Tests
- Test individual functions and classes in isolation
- Mock external dependencies (Redis, Home Assistant API)
- Fast execution (< 1 second per test)
- High coverage (90%+ for core logic)

### Integration Tests
- Test component interactions
- Use real Redis instance (testcontainers or Docker)
- Mock Home Assistant API
- Test config flow, platforms, coordinator

### Scenario Tests
- End-to-end test scenarios from README.md
- Validate complete workflows
- Test timing sequences
- Test safety mechanisms

### Test Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Core algorithms | 95%+ |
| Valve control | 95%+ |
| Safety logic | 100% |
| Redis client | 90%+ |
| Background jobs | 90%+ |
| Platforms | 80%+ |
| Config flow | 80%+ |

---

## HACS Compatibility

### Required Files

#### `hacs.json`
```json
{
  "name": "Multizone Climate",
  "render_readme": true,
  "domains": ["climate", "sensor", "switch", "binary_sensor"],
  "homeassistant": "2024.1.0"
}
```

#### `info.md`
Markdown file shown in HACS with:
- Brief description
- Features list
- Installation instructions
- Configuration guide
- Screenshots

### HACS Validation

```bash
# Validate HACS compatibility
./scripts/validate_hacs.sh

# Check requirements:
# ✓ hacs.json present
# ✓ manifest.json valid
# ✓ README.md present
# ✓ info.md present
# ✓ No files in root (except allowed)
```

### Release Process

1. Update `CHANGELOG.md`
2. Update version in `manifest.json`
3. Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. GitHub Actions creates release automatically
6. HACS picks up new version

---

## Dependencies

### Python Dependencies (`requirements.txt`)

```txt
redis>=4.5.0
aioredis>=2.0.0
```

### Development Dependencies (`requirements_dev.txt`)

```txt
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
pytest-homeassistant-custom-component>=0.13.0
black>=23.0.0
pylint>=2.17.0
mypy>=1.0.0
pre-commit>=3.0.0
```

### Frontend Dependencies (see `frontend/package.json`)

---

## Configuration File Examples

### Basic Setup (`docs/examples/basic-setup.yaml`)

```yaml
# Example Home Assistant configuration.yaml
# (Most config is done via UI, this is just for reference)

# Redis must be running (via add-on or external)
# No configuration.yaml changes needed - all via UI

# Optional: Customize entity names
homeassistant:
  customize:
    climate.multizone_bedroom:
      friendly_name: "Bedroom Climate"
    sensor.multizone_main_target:
      friendly_name: "Main Target Temperature"
```

### Advanced Setup (`docs/examples/advanced-setup.yaml`)

```yaml
# Example automation using multizone climate
automation:
  - alias: "Notify when zone underheated"
    trigger:
      - platform: state
        entity_id: climate.multizone_bedroom
        attribute: satisfaction
        to: "underheated"
    action:
      - service: notify.mobile_app
        data:
          message: "Bedroom is underheated"

  - alias: "Set night mode temperatures"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id:
            - climate.multizone_bedroom
            - climate.multizone_living_room
        data:
          temperature: 18
```

---

## Additional Notes

### Why Not Home Assistant Add-on?

While a Home Assistant add-on could provide a web UI and bundled Redis, it has significant drawbacks:
- **Limited compatibility**: Only works with Home Assistant Supervisor (not Docker, Core, or Container)
- **Complex architecture**: Requires MQTT or API bridge to communicate with Home Assistant
- **Harder installation**: Two-step process (add-on + integration)
- **Update complexity**: Separate update channels

**The custom integration approach is simpler, more compatible, and follows Home Assistant best practices.**

### Hybrid Approach (Future Consideration)

In the future, we could provide:
1. **Core Integration** (primary, this project)
2. **Optional Add-on** (convenience package including Redis)

The add-on would simply bundle Redis and provide a web UI for configuration, but the core logic would remain in the integration.

### Redis Alternatives (Future)

If Redis dependency becomes problematic, we could:
- Use Home Assistant's built-in recorder/database (SQLite/PostgreSQL)
- Implement lightweight in-memory state management
- Use MQTT for state synchronization

For now, Redis provides the best performance and flexibility for job queuing and locking.

---

## Summary

This project structure provides:
- ✅ **HACS-compatible** custom integration
- ✅ **Full Home Assistant integration** with native entities
- ✅ **Custom frontend** with Lovelace cards
- ✅ **Comprehensive testing** strategy
- ✅ **Professional development** workflow
- ✅ **Clear documentation** and examples
- ✅ **Flexible deployment** (works on all HA installations)

The structure follows Home Assistant best practices and is designed for long-term maintainability and extensibility.

---

## Next Steps

1. **Review this structure** with stakeholders
2. **Confirm architectural decisions** (integration vs add-on)
3. **Begin implementation** starting with:
   - Core logic and algorithms
   - Redis client
   - Basic config flow
   - Climate platform
4. **Iterative development** with continuous testing
5. **HACS submission** once stable

---

**Questions or feedback?** Open an issue on GitHub: https://github.com/Chester929/ha_multizone_climate/issues
