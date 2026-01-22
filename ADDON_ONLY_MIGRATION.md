# Migration to Addon-Only Architecture

> **Latest Update (v2.0.0)**: The addon now automatically installs the custom integration component to `/config/custom_components/` on startup, eliminating manual file copying. See hassio-addon/README.md for current installation instructions.

> **Note**: This document describes a historical migration from MQTT/WebSocket API to an add-on-only architecture with a frontend. The project has since evolved further to use a 2-container add-on (Logic + Redis) with a native Python custom integration. See README.md for the current architecture.

## Summary

This repository was migrated from a multi-integration system (MQTT, HA WebSocket API, Custom Integration) to a Home Assistant addon architecture.

## Changes Made

### 1. Removed Components

#### MQTT Middleware
- Deleted `mqtt-middleware/` directory entirely
- Removed MQTT container from all docker-compose files
- Removed MQTT configuration from addon config.yaml
- Removed MQTT environment variables from .env.example

#### Home Assistant Integration
- Deleted `logic/internal/homeassistant/` directory (client, websocket, integration)
- Removed all HA API endpoints from logic API handlers
- Removed HA configuration from addon config.yaml
- Simplified zone creation/update handlers (no HA entity auto-loading)

#### Documentation
- Removed `HA_SERVICE_API.md`
- Removed `CLIMATE_ENTITY_INTEGRATION.md`
- Removed `INTEGRATION_FIXES.md`

#### Frontend
- Removed `IntegrationConfig.tsx` component
- Removed integrations tab from App.tsx
- Simplified `EntitySelector.tsx` to simple text input
- Removed all integration-related tests

### 2. Updated Components

#### Addon Configuration (hassio-addon/config.yaml)
- Removed MQTT and HA integration options
- Kept only: Redis, Logic (log_level), Frontend (port)
- Verified ingress configuration is intact:
  - `ingress: true`
  - `ingress_port: 8099`
  - `panel_icon: mdi:thermostat-box`
  - `panel_title: Multizone Climate`

#### Logic Server (main.go)
- Removed HA integration initialization
- Removed HA settings loading from Redis
- Simplified to: Redis → Worker Pool → HTTP API

#### API Handlers
- Removed 6 HA-specific endpoints
- Simplified integration settings handlers to return empty/ignored responses
- Updated CreateZoneHandler and UpdateZoneHandler to remove HA integration dependency

#### Docker Compose Files
- Removed mqtt-middleware service from all three files:
  - docker-compose.yml
  - docker-compose.ghcr.yml
  - docker-compose.dev.yml

#### Environment Configuration
- Removed MQTT and HA variables from .env.example
- Kept only: REDIS_PASSWORD, LOG_LEVEL

#### Documentation
- Regenerated README.md with addon-only architecture
- Created new hassio-addon/README.md
- Updated addon description

### 3. Architecture After Migration

```
Home Assistant Addon (Ingress-based)
├── Logic Container (GoLang)
│   ├── Core algorithms
│   ├── Valve management
│   ├── REST API for frontend
│   └── Redis client
├── Frontend Container (TypeScript)
│   ├── Zone management UI
│   ├── Statistics & monitoring
│   └── Manual entity ID entry
└── Redis Container (Bundled)
    ├── State storage
    ├── Configuration
    └── Job queues
```

### 4. Integration with Home Assistant

The addon integrates with Home Assistant through:

1. **Native Addon Ingress**
   - Accessed via HA sidebar panel
   - No external ports required (though 8099 is exposed)
   - Seamless HA authentication

2. **Manual Entity References**
   - Users enter entity IDs manually (e.g., `sensor.bedroom_temp`)
   - No auto-discovery or API calls to HA
   - No new entities created in HA

3. **Addon Configuration**
   - Configured through HA addon UI
   - Options: Redis mode, log level, frontend port
   - Simple and straightforward

## Verification

### Addon Integration Verified ✅
- Ingress: Enabled (lines 41-45 in config.yaml)
- Panel: Configured with icon and title
- Configuration: Simplified to essential options
- No external dependencies: MQTT broker or HA API not required

### Code Cleanup Verified ✅
- No MQTT references in source code (only in simplified handlers)
- No HA integration imports in Go code
- Frontend integration tab removed
- EntitySelector simplified to text input

### Documentation Updated ✅
- README.md reflects addon-only architecture
- Addon-specific README created
- Architecture diagrams updated
- FAQ section added

## Usage for End Users

### Installation
1. Add repository to HA addon store
2. Install "Multizone Climate" addon
3. Configure options (Redis, log level)
4. Start addon
5. Access via HA sidebar panel

### Zone Configuration
1. Open addon UI
2. Add zones with:
   - Zone name
   - Temperature sensor entity ID (manual entry)
   - Valve switch entity ID (manual entry)
   - Target temperature
   - Priority
3. Configure main climate settings
4. Monitor statistics

## Benefits of Addon-Only Approach

1. **Simplicity**: No external MQTT broker or API tokens required
2. **Native Integration**: Uses HA's built-in addon system
3. **Security**: Runs within HA's supervised environment
4. **Ease of Use**: Accessed directly from HA sidebar
5. **Maintainability**: Less code, fewer dependencies
6. **Reliability**: No external service dependencies

## Files Changed

### Deleted (19 files)
- mqtt-middleware/ (entire directory)
- logic/internal/homeassistant/ (entire directory)
- HA_SERVICE_API.md
- CLIMATE_ENTITY_INTEGRATION.md
- INTEGRATION_FIXES.md
- frontend/src/client/components/IntegrationConfig.tsx
- frontend/src/client/components/__tests__/IntegrationConfig.test.tsx
- frontend/src/client/components/__tests__/EntitySelector.test.tsx
- logic/internal/api/handlers_ha_entities_test.go
- tests/integration/tests/mqtt-tests.js

### Modified (12 files)
- hassio-addon/config.yaml
- hassio-addon/run
- hassio-addon/README.md
- logic/cmd/server/main.go
- logic/internal/api/handlers.go
- frontend/src/client/components/App.tsx
- frontend/src/client/components/EntitySelector.tsx
- docker-compose.yml
- docker-compose.ghcr.yml
- docker-compose.dev.yml
- .env.example
- README.md

## Migration Complete

The repository is now a pure Home Assistant addon with no external integration dependencies. All MQTT and HA API integration code has been removed, and the system works solely as a containerized addon accessed through HA's ingress system.
