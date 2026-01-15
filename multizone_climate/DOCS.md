# Multizone Climate Add-on

Advanced HVAC zone management with Redis-backed automation for multi-room heating and cooling control.

## About

This add-on provides a complete solution for managing multiple heating/cooling zones in your Home Assistant setup. It includes:

- **Redis Server**: For state management and job queuing
- **Custom Integration**: Multizone Climate custom component for Home Assistant
- **Zone Management**: Control individual room temperatures while optimizing your main HVAC system

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure the add-on (see Configuration section below)
4. Start the add-on
5. If auto-install is enabled, restart Home Assistant to load the integration
6. Go to Settings → Devices & Services → Add Integration → Multizone Climate

## Configuration

### Add-on Configuration

```yaml
redis_host: "localhost"
redis_port: 6379
redis_password: ""
redis_db: 0
redis_key_prefix: "ha_multizone"
install_integration: true
log_level: "info"
```

#### Options

- **redis_host** (required): Redis server hostname (default: "localhost")
- **redis_port** (required): Redis server port (default: 6379)
- **redis_password** (optional): Redis authentication password
- **redis_db** (required): Redis database number 0-15 (default: 0)
- **redis_key_prefix** (required): Prefix for all Redis keys (default: "ha_multizone")
- **install_integration** (required): Auto-install the custom integration (default: true)
- **log_level** (required): Logging level - debug, info, warning, or error (default: "info")

### Integration Configuration

After the add-on is running, configure the integration through the Home Assistant UI:

1. **Redis Connection**: Already configured by the add-on
2. **Main Climate Entity**: Select your main HVAC thermostat entity
3. **Automation Settings**:
   - Calculation mode (slider-based or average)
   - Minimum valves to keep open
   - Temperature ranges and thresholds
   - Timing parameters

4. **Add Climate Zones**: After initial setup, add zones for each room:
   - Zone name
   - Temperature sensor entity
   - Valve switch entity
   - Temperature offsets and thresholds

## Features

### Main Climate Management
- Automatically adjusts main thermostat based on zone demands
- Supports both heating and cooling modes
- Configurable calculation methods (slider-based or average)

### Zone Control
- Individual temperature targets per room
- Automatic valve control based on satisfaction states
- Priority-based zone management
- Hysteresis to prevent valve chattering

### Safety Features
- Minimum valve enforcement (prevents HVAC damage)
- Open-first-then-close valve sequencing
- Valve actuation delays to prevent wear
- Automatic fallback valve activation

### Advanced Features
- Redis-backed state management
- Background job processing with locks
- Configurable timing and thresholds
- Multi-language support (EN, CZ, SK, PL planned)

## How It Works

1. **Temperature Monitoring**: Each zone monitors its temperature sensor
2. **Satisfaction Calculation**: Zones calculate if they are underheated, satisfied, or overheated
3. **Main Target Calculation**: System determines optimal main thermostat temperature
4. **Valve Management**: Zones open/close valves based on heating/cooling needs
5. **Safety Checks**: System ensures minimum valves remain open

## Support

For documentation, issues, and feature requests, visit:
https://github.com/Chester929/ha_multizone_climate

## License

MIT License - see repository for details
