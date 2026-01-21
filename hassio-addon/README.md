# Multizone Climate Add-on

Advanced multi-zone HVAC management for Home Assistant.

## About

This add-on provides intelligent management of multiple heating/cooling zones in your Home Assistant setup. It coordinates zone temperatures, valve control, and main HVAC thermostat settings to optimize comfort and energy efficiency.

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure the add-on (see Configuration section below)
4. Start the add-on
5. Install the Multizone Climate custom integration:
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "Multizone Climate"
   - Follow the configuration wizard

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

## Usage

### Setting Up Zones

After installing both the add-on and custom integration:

1. Open Home Assistant Settings → Devices & Services
2. Find the "Multizone Climate" integration
3. Configure zones through the integration's configuration wizard:
   - Zone Name: Identifier (e.g., "Bedroom")
   - Temperature Sensor: Select from your existing sensors
   - Valve Switch: Select from your existing switches
   - Target Temperature: Desired temperature for this zone
   - Priority: Zone priority (higher priority zones are satisfied first)
4. The integration will create a climate entity for each configured zone

### Managing Zones

- **Through HA Interface**: Use the climate entities created by the integration
- **Direct API**: The add-on exposes a REST API at `http://addon_slug:8080` for advanced usage

### Configuration Options

Global configuration is stored in the add-on and can be accessed via API:
- Main climate entity ID
- Temperature calculation method
- Minimum number of valves that must remain open
- Valve actuation delays
- Safety thresholds

## Features

- **Intelligent Zone Management**: Per-room temperature targets with automatic valve control
- **Safety Features**: Ensures minimum valves stay open to protect HVAC system
- **Smart Algorithms**: Priority-based zone satisfaction and optimal temperature calculation
- **Native HA Integration**: Climate entities for each zone with config flow setup
- **Event-Driven**: Automatic updates when temperature sensors change
- **RESTful API**: Full API access for advanced automation

## Architecture

The system consists of two main components:

1. **Home Assistant Add-on** (2 containers):
   - **Logic Container (GoLang)**: Core algorithms, valve management, safety checks, and REST API
   - **Redis**: State storage, configuration persistence, and job queues

2. **Custom Integration** (Python):
   - Config flow with entity selectors
   - Climate entities (one per zone)
   - Coordinator for polling commands
   - Event-driven temperature synchronization

The add-on runs the backend logic, while the custom integration provides the user interface through native Home Assistant climate entities.

## Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/Chester929/ha_multizone_climate/issues
- Documentation: https://github.com/Chester929/ha_multizone_climate

## License

MIT License
