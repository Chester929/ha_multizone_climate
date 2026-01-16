# Installation Guide

## Prerequisites

- Home Assistant 2024.1.0 or newer
- Redis server (can be installed via Add-on Store)
- Main HVAC climate entity
- Temperature sensors for each zone
- Valve switches for each zone

## Installation via HACS

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three-dot menu and select "Custom repositories"
4. Add repository URL: `https://github.com/Chester929/ha_multizone_climate`
5. Category: Integration
6. Click "Download"
7. Restart Home Assistant

## Manual Installation

1. Download the latest release from GitHub
2. Extract to your Home Assistant config directory:
   ```
   /config/custom_components/multizone_climate/
   ```
3. Restart Home Assistant

## Redis Setup

### For Supervisor Users

1. Go to Settings → Add-ons
2. Search for "Redis"
3. Install and start the Redis add-on
4. Note the connection details (usually localhost:6379)

### For Docker/Core Users

Run Redis in a container:
```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest
```

## Integration Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Multizone Climate"
4. Follow the configuration wizard:
   - Enter Redis connection details
   - Select your main climate entity
   - Configure automation parameters
5. Integration will create the main climate device

## Adding Zones

1. Go to the integration settings
2. Click "Configure"
3. Select "Manage Zones"
4. Add each zone with:
   - Zone name (e.g., "Bedroom")
   - Temperature sensor entity
   - Valve switch entity
   - Zone parameters (offsets, priority, etc.)
5. Repeat for all zones
6. Enable at least one zone to activate multizone feature

## Verification

After setup, verify:
- Main climate device appears in devices list
- Each zone appears as a climate entity
- Temperature sensors are being read
- Multizone enable switch is available

Next: See [Configuration Guide](configuration.md) for parameter tuning.
