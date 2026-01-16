# Multizone Climate - Implementation Guide

This document provides a comprehensive guide for deploying and using the Multizone Climate system.

## Quick Start

### Using Pre-built Multi-architecture Images

The easiest way to get started is using pre-built images from GitHub Container Registry:

```bash
# Clone the repository
git clone https://github.com/Chester929/ha_multizone_climate.git
cd ha_multizone_climate

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services using pre-built images
docker-compose -f docker-compose.ghcr.yml up -d

# Or with MQTT middleware
docker-compose -f docker-compose.ghcr.yml --profile mqtt up -d
```

The images automatically support multiple architectures:
- **amd64** (x86_64)
- **armv7** (32-bit ARM)
- **aarch64** (64-bit ARM)

### Prerequisites

- Docker and Docker Compose installed
- Home Assistant (for integration)
- Redis (bundled or external)
- MQTT Broker (optional, for MQTT integration)

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
   
   # Or with MQTT middleware
   docker-compose --profile mqtt up -d
   ```

4. **Access the frontend**
   - Open http://localhost:8099 in your browser
   - The Logic API is available at http://localhost:8080

### Home Assistant Add-on Installation

1. **Add the repository to Home Assistant**
   - Navigate to Supervisor → Add-on Store
   - Click the menu (⋮) → Repositories
   - Add: `https://github.com/Chester929/ha_multizone_climate`

2. **Install the add-on**
   - Find "Multizone Climate" in the add-on store
   - Click Install

3. **Configure the add-on**
   - Set your preferred options in the Configuration tab
   - Start the add-on

4. **Access the interface**
   - Click "Open Web UI" or use the sidebar panel

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Compose Stack                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Logic      │  │  Frontend    │  │   MQTT       │ │
│  │  (GoLang)    │  │ (TypeScript) │  │ (Optional)   │ │
│  │              │  │              │  │              │ │
│  │  Port: 8080  │  │  Port: 8099  │  │              │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │         │
│         └─────────────────┴──────────────────┘         │
│                           │                            │
│                    ┌──────▼──────┐                     │
│                    │    Redis    │                     │
│                    │  Port: 6379 │                     │
│                    └─────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Components

#### Logic Container (GoLang)
- **Purpose**: Core business logic and algorithms
- **Port**: 8080
- **Key Features**:
  - Main target temperature calculation
  - Valve management and safety checks
  - Background job processing
  - HTTP API for frontend
  - Home Assistant API client

#### Frontend Container (TypeScript/Node.js)
- **Purpose**: Web UI and user interface
- **Port**: 8099
- **Key Features**:
  - Zone management interface
  - Real-time statistics dashboard
  - Configuration management
  - Redis data visualization

#### MQTT Middleware (Node.js) - Optional
- **Purpose**: Bridge between Redis and MQTT
- **Key Features**:
  - Redis to MQTT state synchronization
  - Home Assistant auto-discovery
  - MQTT command handling
  - Topic management

#### Redis
- **Purpose**: Centralized data store
- **Port**: 6379
- **Usage**:
  - Configuration storage
  - Zone state persistence
  - Job queue management
  - Pub/Sub for real-time updates

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
- `LOG_LEVEL`: Logging level (debug, info, warning, error)
- `HTTP_PORT`: HTTP server port (default: 8080)

**Frontend Container:**
- `REDIS_HOST`: Redis server hostname
- `REDIS_PORT`: Redis server port
- `REDIS_PASSWORD`: Redis password (optional)
- `WEB_PORT`: Web server port (default: 8099)
- `LOGIC_API_URL`: Logic container API URL

**MQTT Middleware:**
- `REDIS_HOST`: Redis server hostname
- `REDIS_PORT`: Redis server port
- `REDIS_PASSWORD`: Redis password (optional)
- `MQTT_BROKER`: MQTT broker hostname
- `MQTT_PORT`: MQTT broker port (default: 1883)
- `MQTT_USERNAME`: MQTT username (optional)
- `MQTT_PASSWORD`: MQTT password (optional)
- `MQTT_DISCOVERY_PREFIX`: HA discovery prefix (default: homeassistant)
- `MQTT_TOPIC_PREFIX`: MQTT topic prefix (default: multizone)

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

### Frontend API

**List Zones**
```
GET /api/zones
```

**Get Configuration**
```
GET /api/config
```

**Update Configuration**
```
PUT /api/config
Body: {"use_average_mode": true, "min_valves_open": 2}
```

## Integration with Home Assistant

### Option 1: MQTT Integration (Auto-Discovery)

1. **Enable MQTT in configuration**
   ```yaml
   mqtt:
     enabled: true
     broker: "homeassistant.local"
     port: 1883
   ```

2. **Start with MQTT profile**
   ```bash
   docker-compose --profile mqtt up -d
   ```

3. **Entities will be automatically discovered**:
   - `climate.multizone_bedroom`
   - `sensor.multizone_bedroom_temperature`
   - `binary_sensor.multizone_bedroom_valve`

### Option 2: Home Assistant Service API

1. **Configure entity mappings in Redis**
2. **Use existing Home Assistant entities**
3. **No MQTT broker required**

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
# Check Redis is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test Redis connection
redis-cli -h localhost -p 6379 ping
```

### Logic Container Issues
```bash
# Check logs
docker-compose logs logic

# Verify health
curl http://localhost:8080/health

# Check Redis connection
curl http://localhost:8080/status
```

### Frontend Issues
```bash
# Check logs
docker-compose logs frontend

# Verify health
curl http://localhost:8099/health
```

### MQTT Issues
```bash
# Check MQTT middleware logs
docker-compose logs mqtt-middleware

# Verify MQTT broker connection
mosquitto_sub -h homeassistant.local -t 'multizone/#' -v
```

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

**TypeScript Frontend:**
```bash
cd frontend
npm test
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
├── frontend/              # TypeScript frontend
│   ├── src/
│   │   └── server.ts      # Express server
│   ├── public/
│   │   └── index.html     # Web UI
│   ├── Dockerfile
│   ├── package.json
│   └── tsconfig.json
├── mqtt-middleware/       # MQTT bridge
│   ├── src/
│   │   └── index.js       # Main application
│   ├── Dockerfile
│   └── package.json
├── hassio-addon/          # HA add-on config
│   ├── config.yaml
│   ├── run
│   └── README.md
├── docker-compose.yml
├── .env.example
├── DIAGRAMS.md           # Architecture diagrams
└── README.md
```

## Security Considerations

1. **Redis Password**: Always set a password for Redis in production
2. **Network Security**: Use firewalls to restrict access to container ports
3. **MQTT Credentials**: Use strong passwords for MQTT authentication
4. **Environment Variables**: Never commit sensitive data to version control
5. **TLS/SSL**: Consider using TLS for Redis and MQTT connections

## Performance Tuning

### Redis
- Use Redis persistence (AOF) for critical data
- Monitor memory usage
- Consider Redis clustering for high availability

### Logic Container
- Adjust worker pool size based on load
- Monitor job queue sizes
- Use appropriate log levels (info or warning in production)

### Frontend
- Enable HTTP caching for static assets
- Consider using a reverse proxy (nginx)
- Monitor WebSocket connections

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

See [LICENSE](LICENSE) for license information.

## Support

- **Issues**: https://github.com/Chester929/ha_multizone_climate/issues
- **Discussions**: https://github.com/Chester929/ha_multizone_climate/discussions
- **Documentation**: https://github.com/Chester929/ha_multizone_climate/blob/master/DIAGRAMS.md
