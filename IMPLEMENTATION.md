# Multizone Climate - Implementation Guide

This document provides a comprehensive guide for deploying and using the Multizone Climate system with its 2-container add-on and native Python custom integration.

## Quick Start

### Using Home Assistant Add-on (Recommended)

The easiest way to get started is using the Home Assistant add-on:

1. **Add the repository to Home Assistant**
   - Navigate to Supervisor → Add-on Store
   - Click the menu (⋮) → Repositories
   - Add: `https://github.com/Chester929/ha_multizone_climate`

2. **Install the add-on**
   - Find "Multizone Climate" in the add-on store
   - Click Install

3. **Configure and start the add-on**
   - Set your preferred options in the Configuration tab
   - Start the add-on

4. **Install the Custom Integration**
   - Restart Home Assistant
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "Multizone Climate"
   - Follow the configuration wizard to select entities

### Using Pre-built Multi-architecture Images (Development)

For development or standalone deployment:

```bash
# Clone the repository
git clone https://github.com/Chester929/ha_multizone_climate.git
cd ha_multizone_climate

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services using pre-built images
docker-compose -f docker-compose.ghcr.yml up -d
```

The images automatically support multiple architectures:
- **amd64** (x86_64)
- **armv7** (32-bit ARM)
- **aarch64** (64-bit ARM)

### Prerequisites

- Docker and Docker Compose installed (for standalone deployment)
- Home Assistant (for integration)
- Redis (bundled in add-on)

### Local Development (Building from Source)

1. **Clone the repository**
   ```bash
   git clone https://github.com/Chester929/ha_multizone_climate.git
   cd ha_multizone_climate
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start the services**
   ```bash
   # Start with bundled Redis (default)
   docker-compose up -d
   ```

4. **Access the Logic API**
   - The Logic API is available at http://localhost:8080

## Architecture Overview

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

### Components

#### Logic Container (GoLang)
- **Purpose**: Core business logic and algorithms
- **Port**: 8080
- **Key Features**:
  - Main target temperature calculation
  - Valve management and safety checks
  - Background job processing
  - HTTP API for integration
  - Redis state management

#### Redis
- **Purpose**: Centralized data store
- **Port**: 6379 (internal)
- **Usage**:
  - Configuration storage
  - Zone state persistence
  - Job queue management
  - Command queue for integration

#### Custom Integration (Python)
- **Purpose**: Native Home Assistant integration
- **Key Features**:
  - Multi-step config flow with entity selectors
  - Climate entities for each zone
  - Coordinator for polling commands
  - Event-driven temperature sensor sync
  - Native HA service call integration

## Configuration

### Redis Data Schema

The system uses Redis with the following key structure:

```yaml
# Global Configuration
multizone:config:
  main_climate_entity_id: "climate.main_thermostat"
  use_average_mode: false
  min_valves_open: 1
  main_min_temp: 18.0
  main_max_temp: 30.0
  main_change_threshold: 0.5

# Zone Configuration (example: bedroom)
multizone:zone:bedroom:
  id: "bedroom"
  name: "Bedroom"
  enabled: true
  temperature_sensor_entity_id: "sensor.bedroom_temperature"
  valve_switch_entity_id: "switch.bedroom_valve"
  target_temperature: 22.0
  opening_offset: 0.3
  closing_offset: 0.3
  is_fallback_valve: true
  priority: 10
```

### Environment Variables

**Logic Container:**
- `REDIS_HOST`: Redis server hostname (default: redis)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_PASSWORD`: Redis password (optional)
- `LOG_LEVEL`: Logging level (debug, info, warn, error) (default: info)
- `HTTP_PORT`: HTTP server port (default: 8080)

## API Documentation

### Logic Container REST API

**Health Check**
```
GET /health
Response: {"status": "healthy", "time": "2026-01-15T18:00:00Z"}
```

**System Status**
```
GET /status
Response: {"status": "running", "redis": "connected", "time": "..."}
```

**List Zones**
```
GET /api/zones
Response: [{"id": "bedroom", "name": "Bedroom", ...}, ...]
```

**Get Zone**
```
GET /api/zones/{id}
Response: {"id": "bedroom", "name": "Bedroom", ...}
```

**Update Zone**
```
PUT /api/zones/{id}
Body: {"target_temperature": 22.5, "enabled": true}
Response: {"status": "updated"}
```

**Calculate Main Temperature**
```
POST /api/calculate
Response: {"status": "calculated", "message": "Temperature calculation triggered"}
```

**Get Commands (for integration)**
```
GET /api/commands
Response: {"commands": [{"type": "set_valve", "zone_id": "bedroom", "state": "on"}, ...]}
```

**Update State (from integration)**
```
POST /api/state
Body: {"zone_id": "bedroom", "current_temperature": 21.5}
Response: {"status": "updated"}
```

## Integration with Home Assistant

### Custom Integration Setup

The system uses a native Python custom integration:

1. **Install the add-on** (contains Logic + Redis containers)

2. **Install the custom integration**:
   - Option A: Through HACS (when published)
   - Option B: Manual installation
     ```bash
     # Copy custom_components/multizone_climate to your HA config directory
     cp -r custom_components/multizone_climate /config/custom_components/
     ```

3. **Restart Home Assistant**

4. **Add the integration**:
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "Multizone Climate"

5. **Configure through the wizard**:
   - **Step 1**: Connection settings (add-on URL, typically `http://addon_slug:8080`)
   - **Step 2**: Main climate entity selection (searchable selector)
   - **Step 3**: Zone configuration (for each zone):
     - Zone name
     - Temperature sensor (searchable selector)
     - Valve switch (searchable selector)
     - Target temperature
     - Opening/closing offsets
     - Priority
     - Fallback valve option

6. **The integration will**:
   - Create one climate entity per zone
   - Poll the add-on for valve commands (configurable interval)
   - Push temperature sensor changes to the add-on
   - Execute valve on/off commands via service calls

## Algorithms

### Main Target Temperature Calculation

The system calculates the main thermostat target based on all zone demands:

1. **Filter Active Zones**: Exclude overheated zones
2. **Calculate Raw Target**: 
   - Average mode: Average of all target temperatures
   - Slider mode: Interpolate between min/max targets
3. **Round**: Round to 0.5°C increments
4. **Clamp**: Ensure within min/max bounds
5. **Check Threshold**: Only update if change exceeds threshold

### Valve Management

- **Underheated zones**: Open valve
- **Satisfied/Overheated zones**: Close valve
- **Safety check**: Ensure minimum valves always open
- **Valve locking**: Prevent rapid switching with cooldown periods

## Troubleshooting

### Redis Connection Issues
```bash
# Check Redis is running (when using docker-compose)
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test Redis connection
redis-cli -h localhost -p 6379 ping
```

### Logic Container Issues
```bash
# Check logs (docker-compose)
docker-compose logs logic

# Check logs (add-on)
# View through Supervisor → Multizone Climate → Logs

# Verify health
curl http://localhost:8080/health

# Check Redis connection
curl http://localhost:8080/status
```

### Custom Integration Issues

1. **Integration not showing up**:
   - Ensure custom_components/multizone_climate is in the correct location
   - Restart Home Assistant
   - Check Home Assistant logs for errors

2. **Cannot connect to add-on**:
   - Verify add-on is running
   - Check add-on URL in integration configuration
   - For add-on, URL should be `http://addon_slug:8080`

3. **Entities not updating**:
   - Check coordinator polling interval
   - Verify add-on is accessible
   - Check integration logs in Home Assistant

4. **Temperature not syncing**:
   - Verify temperature sensors are configured correctly
   - Check if sensors are updating
   - Review integration logs for state_changed events

### Logging and Debugging

The system supports structured logging with multiple log levels for better debugging and monitoring.

**Log Levels:**
- `DEBUG`: Detailed diagnostic information, including all operations and state changes
- `INFO`: General informational messages about system operation (default)
- `WARN`: Warning messages for non-critical issues
- `ERROR`: Error messages for failures that need attention

**Setting Log Level:**

Via environment variable (recommended):
```bash
# Set in .env file
LOG_LEVEL=debug

# Or set when starting containers
LOG_LEVEL=debug docker-compose up
```

Via docker-compose override:
```yaml
# docker-compose.override.yml
services:
  logic:
    environment:
      - LOG_LEVEL=debug
```

**Viewing Logs:**

```bash
# View all logs
docker-compose logs -f

# View specific container logs with timestamps
docker-compose logs -f --timestamps logic

# View only error and warning logs (when LOG_LEVEL=warn or LOG_LEVEL=error)
LOG_LEVEL=error docker-compose up

# View debug logs for troubleshooting
LOG_LEVEL=debug docker-compose logs -f logic
```

**Log Output Examples:**

```
# INFO level (default)
2026/01/19 17:38:18 [INFO] Loaded configuration: Redis=localhost:6379
2026/01/19 17:38:18 [INFO] Home Assistant integration started successfully

# DEBUG level (verbose)
2026/01/19 17:38:18 [DEBUG] State changed: sensor.living_room_temp -> 21.5
2026/01/19 17:38:18 [DEBUG] Updated zone temperature: multizone:zone:living_room -> 21.50°C
2026/01/19 17:38:18 [DEBUG] Service call successful: switch.turn_on

# WARN level (warnings)
2026/01/19 17:38:18 [WARN] Failed to load integration settings from Redis: connection timeout

# ERROR level (errors only)
2026/01/19 17:38:18 [ERROR] Failed to connect to Redis: connection refused
```

**When to Use Each Log Level:**

- `DEBUG`: Use during development or when investigating specific issues. Shows all operations including state changes, API calls, and internal operations.
- `INFO`: Use in production for normal operation. Shows important events like startup, configuration changes, and connection status.
- `WARN`: Use to see warnings about non-critical issues that might need attention.
- `ERROR`: Use to see only critical errors that require immediate attention.

**Color-Coded Output:**

When running in a terminal, logs are color-coded for better visibility:
- DEBUG: Cyan
- INFO: Green  
- WARN: Yellow
- ERROR: Red

## Development

### Building Containers

```bash
# Build all containers
docker-compose build

# Build specific container
docker-compose build logic
```

### Running Tests

**GoLang Logic:**
```bash
cd logic
go test ./...
```

### Code Structure

```
ha_multizone_climate/
├── logic/                  # GoLang logic container
│   ├── cmd/
│   │   └── server/        # Main application
│   ├── internal/
│   │   ├── api/           # HTTP handlers
│   │   ├── algorithm/     # Core algorithms
│   │   ├── config/        # Configuration
│   │   ├── models/        # Data models
│   │   ├── redis/         # Redis client
│   │   └── worker/        # Background workers
│   ├── Dockerfile
│   ├── go.mod
│   └── go.sum
├── custom_components/     # Python custom integration
│   └── multizone_climate/
│       ├── __init__.py
│       ├── climate.py     # Climate platform
│       ├── config_flow.py # Configuration wizard
│       ├── coordinator.py # Data coordinator
│       └── manifest.json
├── multizone_climate/     # HA add-on directory (at root for HA Supervisor)
│   ├── config.yaml
│   ├── Dockerfile
│   ├── run
│   └── README.md
├── repository.yaml        # HA add-on repository metadata
├── docker-compose.yml
├── .env.example
├── DIAGRAMS.md           # Architecture diagrams
└── README.md
```

## Security Considerations

1. **Redis Password**: Always set a password for Redis in production
2. **Network Security**: Use firewalls to restrict access to container ports
3. **Environment Variables**: Never commit sensitive data to version control
4. **TLS/SSL**: Consider using TLS for Redis connections
5. **Integration Security**: Custom integration uses HA's built-in authentication

## Performance Tuning

### Redis
- Use Redis persistence (AOF) for critical data
- Monitor memory usage
- Consider Redis clustering for high availability

### Logic Container
- Adjust worker pool size based on load
- Monitor job queue sizes
- Use appropriate log levels (info or warning in production)

### Custom Integration
- Adjust coordinator polling interval based on needs
- Monitor Home Assistant performance impact
- Use reasonable update intervals

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

See [LICENSE](LICENSE) for license information.

## Support

- **Issues**: https://github.com/Chester929/ha_multizone_climate/issues
- **Discussions**: https://github.com/Chester929/ha_multizone_climate/discussions
- **Documentation**: https://github.com/Chester929/ha_multizone_climate/blob/master/DIAGRAMS.md
