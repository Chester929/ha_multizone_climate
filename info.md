# Multizone Climate for Home Assistant

A Home Assistant integration for managing multi-zone climate control with coordinated valve management.

## Features

- Multi-zone temperature control with individual zone targets
- Coordinated valve management ensuring minimum flow
- Priority-based zone heating/cooling
- Safety mechanisms to prevent system damage
- Real-time satisfaction state calculation
- Redis-based job queueing and state management
- Custom Lovelace cards for monitoring and control

## Installation

This integration works only together with the Multizone Climate Add-on. Install the add-on first, which will automatically install the custom integration.

### Install via Add-on (Required)

1. Add the repository: `https://github.com/Chester929/ha_multizone_climate`
2. Install the "Multizone Climate" add-on
3. Start the add-on - it will automatically install the integration to `/config/custom_components/`
4. Restart Home Assistant

## Configuration

1. Go to Configuration → Integrations
2. Click "Add Integration"
3. Search for "Multizone Climate"
4. Follow the configuration wizard

## Requirements

- Multizone Climate Add-on (required)
- Main HVAC climate entity
- Temperature sensors for each zone
- Valve switches for each zone

## Documentation

See [README.md](README.md) for comprehensive documentation.
