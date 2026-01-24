# Multizone Climate Add-on Documentation

Advanced multi-zone HVAC management for Home Assistant.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Integration Settings](#integration-settings)
  - [Redis Settings](#redis-settings)
  - [Logic Settings](#logic-settings)
- [Zone Configuration](#zone-configuration)
- [Usage Guide](#usage-guide)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Local Development](#local-development)
- [Troubleshooting](#troubleshooting)
- [Technical Details](#technical-details)

---

## Overview

The Multizone Climate add-on provides intelligent management of multiple heating/cooling zones in your Home Assistant setup. It coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency while ensuring system safety.

### Key Features

- **Intelligent Zone Management**: Per-room temperature targets with automatic valve control
- **Safety Features**: Ensures minimum valves stay open to protect HVAC system
- **Smart Algorithms**: Priority-based zone satisfaction and optimal temperature calculation
- **Native HA Integration**: Climate entities for each zone with config flow setup
- **Event-Driven**: Automatic updates when temperature sensors change
- **RESTful API**: Full API access for advanced automation

### Architecture Components

The system consists of two main components:

1. **Home Assistant Add-on** (2 containers):
   - **Logic Container (GoLang)**: Core algorithms, valve management, safety checks, and REST API
   - **Redis**: State storage, configuration persistence, and job queues

2. **Custom Integration** (Python):
   - Config flow with entity selectors
   - Climate entities (one per zone)
   - Coordinator for polling commands
   - Event-driven temperature synchronization

For detailed architecture diagrams and flows, see [DIAGRAMS.md](https://github.com/Chester929/ha_multizone_climate/blob/main/DIAGRAMS.md).

---

## Installation

### Step 1: Add the Add-on Repository

1. Navigate to **Settings** → **Add-ons** → **Add-on Store**
2. Click the menu icon (⋮) in the top right corner
3. Select **Repositories**
4. Add this URL: `https://github.com/Chester929/ha_multizone_climate`
5. Click **Add**

### Step 2: Install the Add-on

1. Find "Multizone Climate" in the add-on store
2. Click on the add-on
3. Click **INSTALL**
4. Wait for the installation to complete

### Step 3: Configure the Add-on

1. Go to the **Configuration** tab
2. Review and adjust settings as needed (see [Configuration](#configuration) section)
3. Click **SAVE**

### Step 4: Start the Add-on

1. Go to the **Info** tab
2. Click **START**
3. Check the **Log** tab to verify successful startup
4. Look for the message: "Custom component installed successfully!"

The add-on automatically installs the custom integration to `/config/custom_components/multizone_climate/`.

### Step 5: Restart Home Assistant

1. Navigate to **Settings** → **System**
2. Click **RESTART**
3. Wait for Home Assistant to restart

### Step 6: Configure Zones

1. Go to **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for "Multizone Climate"
4. Follow the configuration wizard to add zones (see [Zone Configuration](#zone-configuration))

---

## Configuration

The add-on can be configured through the **Configuration** tab in the add-on interface.

### Integration Settings

```yaml
integration:
  coordinator_interval: 30  # Seconds between command checks (5-300)
  backend_port: 8080        # Backend API port (1024-65535)
```

#### coordinator_interval

- **Description**: How often (in seconds) the custom integration polls the backend for commands to execute
- **Type**: Integer
- **Range**: 5-300 seconds
- **Default**: 30 seconds
- **Note**: Lower values provide faster response but increase system load. Requires add-on restart to apply changes.

#### backend_port

- **Description**: Port for the backend API server
- **Type**: Port number
- **Range**: 1024-65535
- **Default**: 8080
- **Note**: Ensure this port is not used by other services. Requires add-on restart to apply changes.

### Redis Settings

```yaml
redis:
  mode: bundled  # Options: bundled or external
  host: ""       # Required if mode is external
  port: 6379     # Required if mode is external
  password: ""   # Optional Redis password
```

#### mode

- **Description**: Redis connection mode
- **Options**: `bundled` or `external`
- **Default**: `bundled`
- **bundled**: Uses the built-in Redis container (recommended for most users)
- **external**: Connects to an external Redis server

#### host

- **Description**: Redis server hostname or IP address
- **Type**: String
- **Required**: Yes, when mode is `external`
- **Example**: `192.168.1.100` or `redis.local`

#### port

- **Description**: Redis server port
- **Type**: Port number
- **Default**: 6379
- **Required**: Yes, when mode is `external`

#### password

- **Description**: Redis authentication password
- **Type**: Password (string)
- **Required**: No
- **Default**: Empty (no authentication)
- **Note**: Recommended for external Redis servers

### Logic Settings

```yaml
logic:
  log_level: info  # Options: debug, info, warning, error
```

#### log_level

- **Description**: Logging verbosity for the logic container
- **Options**: `debug`, `info`, `warning`, `error`
- **Default**: `info`
- **debug**: Detailed debugging information (verbose)
- **info**: General informational messages (recommended)
- **warning**: Warning messages only
- **error**: Error messages only

---

## Zone Configuration

Zones are configured through the custom integration's config flow interface.

### Adding Your First Zone

1. After installing the integration, you'll be prompted to select the main climate entity
2. Choose your existing HVAC thermostat entity (e.g., `climate.main_thermostat`)
3. Configure your first zone with the following fields:

#### Zone Fields

**Zone Name**
- **Description**: Friendly name for the zone
- **Type**: String
- **Example**: "Living Room", "Bedroom", "Kitchen"

**Temperature Sensor**
- **Description**: Entity providing the current temperature for this zone
- **Type**: Entity selector (filtered to temperature sensors)
- **Example**: `sensor.living_room_temperature`
- **Note**: Must be a sensor with device_class: temperature

**Valve Switch**
- **Description**: Switch or valve entity controlling the zone's heating/cooling valve
- **Type**: Entity selector (filtered to switches and valves)
- **Example**: `switch.living_room_valve`
- **Note**: Can be a switch, valve, or other binary control entity

**Target Temperature**
- **Description**: Desired temperature for this zone
- **Type**: Float (°C)
- **Default**: 20.0°C
- **Note**: Can be adjusted later through the climate entity

**Priority**
- **Description**: Zone importance (higher priority zones are satisfied first)
- **Type**: Integer
- **Range**: 0-100
- **Default**: 50
- **Note**: Higher values = higher priority

### Adding Additional Zones

After configuring the first zone, you'll be prompted to add more zones. Repeat the process for each room you want to control.

### Managing Zones

Once configured, each zone gets its own climate entity (e.g., `climate.multizone_living_room`) that can be controlled through:
- Home Assistant UI
- Automations
- Scripts
- The REST API

---

## Usage Guide

### Controlling Zones

Each configured zone has a climate entity that supports:
- **Setting target temperature**: Adjust the desired temperature
- **Viewing current temperature**: See the current reading from the zone's sensor
- **HVAC mode**: Reflects the mode of the main thermostat
- **State**: Shows if the zone is heating, cooling, or idle

### Understanding System Behavior

The add-on continuously:
1. **Monitors** all zone temperatures
2. **Calculates** which zones need heating/cooling
3. **Determines** which valves should be open/closed
4. **Calculates** the optimal main thermostat target temperature
5. **Sends commands** to the integration to execute

The custom integration:
1. **Polls** the backend for commands (every `coordinator_interval` seconds)
2. **Executes** service calls to control valves and the main thermostat
3. **Pushes** temperature updates to the backend when sensors change

### Safety Features

The system includes built-in safety features:
- **Minimum valves open**: Ensures at least one valve stays open to protect the HVAC system
- **Fallback valve**: Automatically activates a designated valve when all zones are satisfied
- **Valve actuation delays**: Prevents rapid valve switching that could cause wear
- **Open-first-then-close sequencing**: New valves open before others close

---

## Architecture

### Component Communication

```
Temperature Sensor (HA)
    ↓ (state change event)
Custom Integration
    ↓ (POST /api/state)
Logic Container (Backend)
    ↓ (processes, calculates)
Redis (State Storage)
    ↓ (stores commands)
Custom Integration (Coordinator polls)
    ↓ (GET /api/commands)
Logic Container
    ↓ (returns commands)
Custom Integration
    ↓ (executes service calls)
Valve Switches & Main Climate (HA)
```

### Data Flow

1. **Temperature Updates**: Event-driven push from integration to backend
2. **Command Polling**: Integration polls backend at configured interval
3. **State Storage**: All zone state and configuration stored in Redis
4. **Job Processing**: Background jobs for calculation, valve management, and safety checks

For detailed architecture diagrams, refer to [DIAGRAMS.md](https://github.com/Chester929/ha_multizone_climate/blob/main/DIAGRAMS.md).

---

## API Reference

The add-on exposes a REST API on port 8080 (configurable). The custom integration uses this API, but it's also available for advanced automation.

### Base URL

```
http://homeassistant.local:8080
```

Or within Home Assistant:
```
http://localhost:8080
```

### Core Endpoints

#### Health Check

**GET** `/health`

Returns the health status of the logic service.

**Response:**
```json
{
  "status": "healthy",
  "redis": "connected"
}
```

#### List Zones

**GET** `/api/zones`

Returns all configured zones.

**Response:**
```json
{
  "zones": [
    {
      "id": "living_room",
      "name": "Living Room",
      "temperature_sensor_id": "sensor.living_room_temperature",
      "valve_entity_id": "switch.living_room_valve",
      "target_temperature": 21.5,
      "priority": 50,
      "enabled": true
    }
  ]
}
```

#### Get Commands (Integration)

**GET** `/api/commands`

Returns pending commands for the integration to execute.

**Response:**
```json
{
  "commands": [
    {
      "type": "set_valve",
      "zone_id": "living_room",
      "entity_id": "switch.living_room_valve",
      "state": "on"
    },
    {
      "type": "set_climate",
      "entity_id": "climate.main_thermostat",
      "temperature": 22.0
    }
  ]
}
```

#### Post State (Integration)

**POST** `/api/state`

Pushes current state from integration to backend.

**Request:**
```json
{
  "zones": [
    {
      "id": "living_room",
      "current_temperature": 20.5,
      "valve_state": "on"
    }
  ],
  "main_climate": {
    "current_temperature": 21.0,
    "mode": "heat"
  }
}
```

### Statistics API

For detailed statistics and metrics endpoints, see the [Statistics](#statistics-and-metrics) section.

### Valve Management

For details on valve control algorithms and safety features, see the [Valve Management](#valve-management) section.

### Multi-Architecture Docker Builds

For information about building Docker images for different architectures, see the [Docker Builds](#docker-builds) section.

---

## Local Development

### Prerequisites

- Docker and Docker Compose
- Go 1.21+ (for logic container development)
- Python 3.11+ (for custom integration development)
- Make (optional, for convenience commands)

### Using VS Code Devcontainer

The recommended way to develop is using the VS Code devcontainer setup (see [Local Testing Setup](#local-testing-setup) section).

### Using Docker Compose

For quick local testing without the full devcontainer:

#### Start All Services

```bash
docker compose up -d
```

#### View Logs

```bash
docker compose logs -f
```

#### Check Service Status

```bash
docker compose ps
```

#### Stop Services

```bash
docker compose down
```

### Using Make Commands

The repository includes a Makefile with helpful commands:

```bash
# Build containers
make build

# Start services
make start

# View logs
make logs

# Run tests
make test-logic

# Connect to Redis CLI
make redis-cli

# Check service health
make status
```

For a full list of commands:
```bash
make help
```

### Testing

#### Run Go Unit Tests

```bash
cd logic
go test ./...
```

#### Run Integration Tests

```bash
make test-integration
```

#### Run Python Custom Integration Tests

```bash
pytest tests/custom_components/
```

### Building the Add-on Locally

To build the add-on locally using the Home Assistant builder tool:

```bash
docker run \
  --rm \
  -it \
  --privileged \
  -v $(pwd)/multizone_climate:/data \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  ghcr.io/home-assistant/amd64-builder \
  -t /data \
  --amd64 \
  --test
```

Replace `--amd64` with `--armv7`, `--aarch64`, or `--all` for other architectures.

---

## Troubleshooting

### Add-on Won't Start

**Symptoms:**
- Add-on fails to start or crashes immediately
- Error messages in the add-on logs

**Solutions:**
1. Check the add-on logs for specific error messages
2. Verify Redis configuration (if using external Redis)
3. Ensure port 8080 is not in use by another service
4. Check system resources (RAM, disk space)
5. Try changing the backend_port in configuration

### Integration Can't Connect to Backend

**Symptoms:**
- Integration shows as "unavailable"
- Error messages about connection refused or timeout

**Solutions:**
1. Verify the add-on is running (check add-on status)
2. Check add-on logs for backend startup errors
3. Ensure `backend_port` in add-on config matches what the integration expects
4. Restart both the add-on and Home Assistant

### Commands Not Executing

**Symptoms:**
- Zone temperatures not being controlled
- Valves not opening/closing as expected
- Main thermostat not being adjusted

**Solutions:**
1. Check the `coordinator_interval` setting (might be too long)
2. Verify entities are accessible and responsive
3. Check Home Assistant logs for service call errors
4. Enable debug logging in the integration
5. Verify the backend is generating commands (check API at `/api/commands`)

### Zone Not Responding

**Symptoms:**
- Specific zone not being controlled
- Zone shows as "unavailable"

**Solutions:**
1. Verify the temperature sensor is working and reporting values
2. Check the valve entity is accessible and responsive
3. Ensure the zone is enabled (check via API or integration)
4. Verify entity IDs haven't changed in Home Assistant
5. Check backend logs for errors related to the zone

### Enable Debug Logging

To enable detailed logging for the custom integration:

1. Edit `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug
```

2. Restart Home Assistant
3. Check logs in **Settings** → **System** → **Logs**

To enable debug logging for the add-on:

1. Go to add-on **Configuration** tab
2. Set `log_level: debug`
3. Click **SAVE**
4. Restart the add-on
5. Check add-on logs

### Common Error Messages

**"Redis connection failed"**
- Check Redis mode and connection settings
- If using external Redis, verify host and port are correct
- Check network connectivity to Redis server

**"Port 8080 already in use"**
- Another service is using the port
- Change `backend_port` in add-on configuration to a different port

**"Entity not found"**
- Entity ID has changed or doesn't exist
- Reconfigure the integration with correct entity IDs

**"Valve actuation too frequent"**
- Valve is being actuated too quickly (safety feature)
- This is normal behavior to prevent valve wear
- Adjust valve actuation delay if needed (via API)

---

## Technical Details

### Valve Management

The add-on includes sophisticated valve management features:

#### Valve Actuation Delay

Prevents rapid valve state changes that cause mechanical wear:
- Each zone tracks when its valve was last actuated
- Configurable minimum time between valve operations (default: 30 seconds)
- Applies to both open and close operations

#### Valve Lock Mechanism

Allows temporary locking of valves during maintenance:
- Locks can be set with expiration timestamps
- Automatic expiration when time passes
- Prevents operations while locked

#### Chattering Prevention

Hysteresis logic prevents valves from rapidly switching:
- Different thresholds for opening vs closing
- Temperature must change sufficiently before valve state changes
- Configurable per zone

#### Open-First-Then-Close Sequencing

Safety feature for valve management:
- New valves open before existing valves close
- Ensures at least one valve is always open during transitions
- Prevents HVAC damage from closed circulation

For detailed algorithms and flowcharts, see [DIAGRAMS.md](https://github.com/Chester929/ha_multizone_climate/blob/main/DIAGRAMS.md).

### Statistics and Metrics

The add-on tracks historical data for analysis:

#### Temperature History

**Endpoint:** `GET /api/statistics/zones/{id}/temperature?hours=24`

Returns temperature readings over time for a zone.

**Query Parameters:**
- `hours`: Number of hours of history (default: 24, max: 720)

#### Valve Activity History

**Endpoint:** `GET /api/statistics/zones/{id}/valve-activity?hours=24`

Returns valve state change history for a zone.

#### Energy Consumption Estimates

**Endpoint:** `GET /api/statistics/zones/{id}/energy?hours=24`

Provides estimated energy consumption based on valve activity and temperature differentials.

#### System Performance Metrics

**Endpoint:** `GET /api/metrics`

Returns overall system performance metrics:
- Total zones configured
- Active zones count
- Average response time
- Command execution rate
- Error rate

### Docker Builds

The Logic container supports multi-architecture builds:

#### Supported Architectures

- **linux/amd64** (x86_64) - Standard desktop/server systems
- **linux/arm/v7** (armv7) - 32-bit ARM devices (Raspberry Pi 2/3)
- **linux/arm64** (aarch64) - 64-bit ARM devices (Raspberry Pi 4)

#### Container Images

| Component | Image | Registry |
|-----------|-------|----------|
| Logic Container | `multizone-logic` | Built from source |
| Redis | `redis:latest` | Docker Hub (official) |

#### Building for Specific Architecture

For amd64:
```bash
docker build \
  --build-arg BUILD_FROM="ghcr.io/home-assistant/amd64-base:3.19" \
  -t local/multizone-logic:amd64 \
  -f logic/Dockerfile \
  .
```

For armv7:
```bash
docker build \
  --build-arg BUILD_FROM="ghcr.io/home-assistant/armv7-base:3.19" \
  -t local/multizone-logic:armv7 \
  -f logic/Dockerfile \
  .
```

#### GitHub Actions Build

The repository includes automated GitHub Actions workflows for:
- Multi-architecture builds on pushes to main branches
- Pull request validation builds
- Semantic version tagging

Images are published to GitHub Container Registry (GHCR).

---

## Additional Resources

- **GitHub Repository**: https://github.com/Chester929/ha_multizone_climate
- **Issues**: https://github.com/Chester929/ha_multizone_climate/issues
- **Architecture Diagrams**: [DIAGRAMS.md](https://github.com/Chester929/ha_multizone_climate/blob/main/DIAGRAMS.md)

---

## Support

For help and support:

1. **Check this documentation** first
2. **Review the [Troubleshooting](#troubleshooting)** section
3. **Check existing GitHub Issues** for similar problems
4. **Open a new issue** on GitHub with:
   - Description of the problem
   - Add-on version
   - Home Assistant version
   - Relevant logs (with sensitive information removed)
   - Steps to reproduce

---

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/Chester929/ha_multizone_climate/blob/main/LICENSE) file for details.
