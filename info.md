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

### Via HACS (Recommended)

1. Open HACS
2. Go to Integrations
3. Click the 3-dot menu and select "Custom repositories"
4. Add `https://github.com/Chester929/ha_multizone_climate`
5. Category: Integration
6. Click "Add"
7. Find "Multizone Climate" and install

### Manual

1. Copy `custom_components/multizone_climate` to your HA config directory
2. Restart Home Assistant

## Configuration

1. Go to Configuration → Integrations
2. Click "Add Integration"
3. Search for "Multizone Climate"
4. Follow the configuration wizard

## Requirements

- Redis server (install via Add-on Store for Supervisor users)
- Main HVAC climate entity
- Temperature sensors for each zone
- Valve switches for each zone

## Documentation

See [README.md](README.md) for comprehensive documentation.
