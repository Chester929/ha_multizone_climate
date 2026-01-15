# Multizone Climate Add-on

![Multizone Climate Logo](logo.png)

## Installation Methods

This project can be installed in two ways:

### Method 1: Home Assistant Add-on (Recommended)

The add-on bundles everything you need, including Redis.

1. Add this repository to your Home Assistant add-on store
2. Install the "Multizone Climate" add-on
3. Configure and start the add-on
4. The integration will be automatically installed
5. Restart Home Assistant
6. Configure through Settings → Devices & Services

**Benefits:**
- Redis included and pre-configured
- One-click installation
- Automatic integration setup
- Easy updates through the add-on store

### Method 2: HACS Custom Integration

Install just the integration via HACS if you already have Redis running.

1. Install via HACS or copy `custom_components/multizone_climate` to your config folder
2. Ensure you have a Redis server running
3. Restart Home Assistant
4. Add integration through Settings → Devices & Services
5. Configure Redis connection and settings

**Benefits:**
- Use your existing Redis instance
- Smaller footprint
- More control over Redis configuration

## Quick Start

### For Add-on Users

1. Install and start the add-on
2. Configure add-on options (Redis settings)
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Multizone Climate"
6. Follow the configuration wizard:
   - Select your main HVAC climate entity
   - Configure automation settings
7. Add climate zones for each room
8. Enable the multizone feature when ready

### For HACS Users

1. Ensure Redis is running and accessible
2. Install the integration
3. Configure through the UI with your Redis connection details
4. Follow the same steps as above from step 6

## Documentation

- [Complete Documentation](README.md) - Full system documentation
- [Diagrams](DIAGRAMS.md) - Visual system architecture and algorithms
- [Add-on Documentation](multizone_climate/DOCS.md) - Add-on specific guide

## Features

- **Multi-zone heating/cooling control** - Manage different temperatures per room
- **Intelligent valve management** - Automatic opening/closing based on zone needs
- **Safety features** - Minimum valve enforcement, delay sequencing
- **Redis-backed state** - Reliable state management and job queuing
- **Priority-based control** - Configure which zones get heating/cooling first
- **Hysteresis control** - Prevent valve chattering and wear
- **Multiple calculation modes** - Slider-based or average temperature calculation
- **Comprehensive monitoring** - Sensors for debugging and monitoring

## System Requirements

- Home Assistant OS, Supervised, or Container installation
- Supported architecture: amd64, armv7, aarch64, or i386
- For add-on: 50MB storage, 128MB RAM minimum
- For HACS: External Redis server (version 4.5+)

## Project Structure

```
ha_multizone_climate/
├── README.md                          # This file (updated with install methods)
├── DIAGRAMS.md                        # System diagrams and algorithms
├── multizone_climate/                 # Home Assistant Add-on
│   ├── config.yaml                    # Add-on configuration
│   ├── Dockerfile                     # Container image definition
│   ├── build.yaml                     # Multi-arch build config
│   ├── run.sh                         # Add-on startup script
│   ├── DOCS.md                        # Add-on documentation
│   ├── CHANGELOG.md                   # Add-on changelog
│   ├── icon.png                       # Add-on icon
│   ├── logo.png                       # Add-on logo
│   ├── translations/                  # Add-on UI translations
│   │   └── en.yaml
│   └── custom_components/             # Home Assistant Custom Integration
│       └── multizone_climate/
│           ├── manifest.json          # Integration manifest
│           ├── __init__.py            # Integration entry point
│           ├── config_flow.py         # Configuration UI
│           ├── const.py               # Constants
│           ├── climate.py             # Climate entities
│           ├── sensor.py              # Sensor entities
│           └── switch.py              # Switch entities (multizone enable)
```

## Support

- **Issues**: https://github.com/Chester929/ha_multizone_climate/issues
- **Documentation**: Full docs in this repository
- **Community**: Home Assistant Community Forum

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## Roadmap

- [ ] Complete integration implementation (zones, valves, automations)
- [ ] Add comprehensive tests
- [ ] Implement background job processing
- [ ] Add Lovelace custom cards
- [ ] Support additional languages (CZ, SK, PL)
- [ ] Add heating curve integration
- [ ] Implement PI controller option
- [ ] Add learning/adaptive features
