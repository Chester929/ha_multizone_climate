# Multizone Climate Add-on

Advanced multi-zone HVAC management for Home Assistant.

## About

This add-on provides intelligent management of multiple heating/cooling zones in your Home Assistant setup. It coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency.

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure the addon (see Configuration section below)
4. Start the add-on
5. Access the UI through the Home Assistant sidebar or the "OPEN WEB UI" button

## Configuration

### Integration

```yaml
integration:
  coordinator_interval: 30  # Seconds between command checks (5-300)
  backend_port: 8080        # Backend API port (1024-65535)
```

- **coordinator_interval**: How often (in seconds) the integration polls for commands to execute. Range: 5-300 seconds. Default: 30 seconds. Requires add-on restart to apply changes.
- **backend_port**: Port for the backend API server. Range: 1024-65535. Default: 8080. Requires add-on restart to apply changes.

### Redis

```yaml
redis:
  mode: bundled  # Options: bundled or external
  host: ""       # Required if mode is external
  port: 6379     # Required if mode is external
  password: ""   # Optional Redis password
```

- **mode**: Use bundled Redis (default) or connect to external Redis server
- **host**: Redis host address (only for external mode)
- **port**: Redis port (only for external mode)  
- **password**: Redis authentication password (optional)

### Logic

```yaml
logic:
  log_level: info  # Options: debug, info, warning, error
```

- **log_level**: Set logging verbosity for the logic container

### Frontend

```yaml
frontend:
  port: 8099  # Web interface port
```

- **port**: Port for the web interface (default: 8099)

## Usage

### Accessing the UI

- **Via Sidebar**: Click the "Multizone Climate" panel in your Home Assistant sidebar
- **Via Add-on Page**: Click "OPEN WEB UI" button on the add-on page
- **Direct Access**: Navigate to `http://homeassistant.local:8099` (if port is exposed)

### Creating Zones

1. Open the Multizone Climate UI
2. Click "Add Zone"
3. Enter zone details:
   - Name: Zone identifier (e.g., "Bedroom")
   - Temperature Sensor Entity ID: e.g., `sensor.bedroom_temperature`
   - Valve Switch Entity ID: e.g., `switch.bedroom_valve`
   - Climate Entity ID: (optional) e.g., `climate.bedroom_thermostat`
   - Target Temperature: Desired temperature for this zone
   - Priority: Zone priority (higher priority zones are satisfied first)
4. Save the zone

### Configuration Options

In the Configuration tab, you can:
- Set the main climate entity ID
- Configure temperature calculation method
- Set minimum number of valves that must remain open
- Adjust valve actuation delays
- Configure safety thresholds

## Features

- **Intelligent Zone Management**: Per-room temperature targets with automatic valve control
- **Safety Features**: Ensures minimum valves stay open to protect HVAC system
- **Smart Algorithms**: Priority-based zone satisfaction and optimal temperature calculation
- **Real-time Monitoring**: Live statistics and metrics for all zones
- **Historical Data**: Track temperature and valve activity over time

## Architecture

The add-on consists of three main components:

1. **Logic Container (GoLang)**: Core algorithms, valve management, and safety checks
2. **Frontend (TypeScript)**: Web-based user interface for configuration and monitoring
3. **Redis**: State storage and message queuing

All components run within the add-on and communicate via Redis.

## Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/Chester929/ha_multizone_climate/issues
- Documentation: https://github.com/Chester929/ha_multizone_climate

## License

MIT License
