# Multizone Climate Add-on

Advanced multi-zone HVAC management for Home Assistant.

## Features

- **Containerized Architecture**: Modern microservices design with separate Logic, Frontend, and MQTT containers
- **GoLang Logic Engine**: High-performance core algorithms for temperature calculation and valve management
- **TypeScript Frontend**: Modern web UI for zone management and monitoring
- **Multiple Integration Options**: MQTT, Home Assistant Service API, or native Python integration
- **Smart Algorithms**: Intelligent main target temperature calculation and valve orchestration
- **Safety Features**: Minimum valve enforcement and valve lock mechanisms
- **Real-time Updates**: WebSocket and MQTT Pub/Sub for instant state synchronization

## Configuration

### Redis
- **mode**: Choose `bundled` to use the included Redis container or `external` to use your own Redis server
- **password**: Redis password for security (optional but recommended)

### MQTT (Optional)
- **enabled**: Enable MQTT integration for Home Assistant auto-discovery
- **broker**: MQTT broker address (default: homeassistant.local)
- **port**: MQTT broker port (default: 1883)
- **username**: MQTT username (optional)
- **password**: MQTT password (optional)

### Logic Container
- **log_level**: Logging verbosity (debug, info, warning, error)

### Frontend
- **port**: Web interface port (default: 8099)

## Usage

After installation:

1. Access the web interface through the Home Assistant sidebar
2. Configure your zones with temperature sensors and valve switches
3. Set target temperatures for each zone
4. The system will automatically manage your HVAC based on zone demands

## Documentation

For detailed architecture and algorithm documentation, see [DIAGRAMS.md](https://github.com/Chester929/ha_multizone_climate/blob/master/DIAGRAMS.md)

## Support

For issues and feature requests, visit: https://github.com/Chester929/ha_multizone_climate/issues
