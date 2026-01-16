# Testing with Real Home Assistant Instance

This guide explains how to test the Multizone Climate integration with a real Home Assistant instance.

## Prerequisites

1. **Home Assistant** instance (version 2023.1 or later)
2. **Redis server** (version 6.0 or later)
3. **HVAC system** with Home Assistant integration (e.g., climate entity)
4. **Temperature sensors** for each zone
5. **Valve switches** for each zone (optional, can use virtual switches for testing)

## Installation Methods

### Method 1: HACS Installation (Recommended)

1. Ensure HACS is installed in your Home Assistant
2. Add this repository as a custom repository in HACS:
   - Click on HACS in the sidebar
   - Click on "Integrations"
   - Click the three dots in the top right
   - Select "Custom repositories"
   - Add URL: `https://github.com/Chester929/ha_multizone_climate`
   - Category: Integration
3. Click "Install"
4. Restart Home Assistant

### Method 2: Manual Installation

1. Clone or download this repository
2. Copy the `custom_components/multizone_climate` directory to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Redis Setup

### Docker Installation

```bash
docker run -d \
  --name redis-multizone \
  -p 6379:6379 \
  redis:latest
```

### Standalone Installation

Follow the official Redis installation guide for your operating system:
https://redis.io/docs/getting-started/installation/

## Configuration

### Step 1: Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Multizone Climate"
4. Follow the configuration wizard:

#### Redis Configuration
- **Host**: Your Redis server address (e.g., `localhost` or `192.168.1.100`)
- **Port**: Redis port (default: `6379`)
- **Password**: Redis password (leave empty if not set)
- **Database**: Redis database number (default: `0`)
- **Key Prefix**: Prefix for Redis keys (default: empty)

#### Main Climate Selection
- **Main Climate Entity**: Select your main HVAC climate entity

#### Automation Configuration
- **Use Average Mode**: Toggle between slider mode and average mode
- **Main Target When All Zones Satisfied**: Slider position (0-100%)
- **Minimum Valves Open**: Number of valves to keep open (default: 1)
- **Main Min Temperature**: Minimum temperature for main climate (default: 18.0°C)
- **Main Max Temperature**: Maximum temperature for main climate (default: 30.0°C)
- **Main Change Threshold**: Minimum change to update main target (default: 0.5°C)
- **Valve Actuation Delay**: Delay between valve operations (default: 60s)
- **Coordinator Interval**: Update interval (default: 15s)
- **Satisfaction Epsilon**: Satisfaction temperature tolerance (default: 0.1°C)

### Step 2: Add Zones

1. Go to **Settings** → **Devices & Services**
2. Find the "Multizone Climate" integration
3. Click **Configure**
4. Select **Zones**
5. Click **Add Zone**
6. Configure each zone:
   - **Zone Name**: Friendly name (e.g., "Living Room")
   - **Temperature Sensor**: Select the temperature sensor entity
   - **Valve Switch**: Select the valve switch entity
   - **Target Change Threshold**: Temperature step (default: 0.1°C)
   - **Opening Offset**: Temperature below target to open valve (default: 0.3°C)
   - **Closing Offset**: Temperature above target to close valve (default: 0.3°C)
   - **Priority**: Zone priority (higher = more important)
   - **Is Fallback**: Mark as safety fallback valve

## Testing Scenarios

### Scenario 1: Basic Temperature Control

1. Set different target temperatures for each zone
2. Observe that the main climate target adjusts automatically
3. Watch valve states change based on zone satisfaction

### Scenario 2: Minimum Valve Enforcement

1. Set all zones to high target temperatures (satisfied/overheated)
2. Verify that at least one valve (fallback) remains open
3. Check system logs for safety valve messages

### Scenario 3: Priority System

1. Create zones with different priorities
2. When multiple zones need heating/cooling
3. Verify higher priority zones are served first

### Scenario 4: Hysteresis Behavior

1. Set a zone target temperature
2. Observe temperature rise/fall
3. Note that valve doesn't oscillate rapidly (hysteresis working)
4. Check satisfaction state transitions (underheated → satisfied → overheated)

### Scenario 5: Mode Switching

1. Test HVAC mode changes (heat → cool → off)
2. Verify multizone adjusts logic appropriately
3. Check that cooling mode reverses satisfaction logic

## Verification Checklist

- [ ] Redis connection successful
- [ ] Main climate entity shows current data
- [ ] Zone climate entities created successfully
- [ ] Zone target temperature can be changed via UI
- [ ] Main climate target updates when zone targets change
- [ ] Valves open/close based on zone satisfaction
- [ ] Minimum valve requirement is enforced
- [ ] Coordinator updates every 15 seconds
- [ ] Automations trigger on temperature changes
- [ ] Safety checks run periodically
- [ ] Frontend cards display correctly
- [ ] No errors in Home Assistant logs

## Monitoring

### Entity States

Check the following entities in **Developer Tools** → **States**:

- `climate.multizone_climate_main` - Main climate device
- `climate.<zone_name>` - Each zone climate entity
- `sensor.multizone_*` - Various sensors
- `binary_sensor.multizone_*` - Status sensors
- `switch.multizone_*` - Control switches

### Redis Data

Connect to Redis and inspect keys:

```bash
redis-cli
KEYS multizone:*
GET multizone:config
HGETALL multizone:zones:zone_1
```

### Logs

Monitor Home Assistant logs for multizone activity:

```bash
tail -f /config/home-assistant.log | grep multizone
```

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug
```

## Troubleshooting

### Redis Connection Issues

- Verify Redis is running: `redis-cli ping` (should return PONG)
- Check firewall settings
- Verify host and port in configuration

### Valve Not Responding

- Check valve switch entity is working independently
- Verify valve actuation delay hasn't prevented operation
- Check valve lock status in Redis

### Main Temperature Not Updating

- Verify main change threshold isn't too high
- Check that zones are active (not all OFF)
- Ensure at least one zone is underheated/undercooled

### Frontend Cards Not Loading

- Clear browser cache
- Check browser console for JavaScript errors
- Verify custom cards are registered: `window.customCards`

## Performance Testing

### Load Testing

1. Create 10+ zones
2. Monitor coordinator update times
3. Check Redis memory usage
4. Verify job queue processing

### Stress Testing

1. Rapidly change multiple zone targets
2. Monitor job queue length
3. Verify no deadlocks or race conditions
4. Check system responsiveness

## Recommended Configuration

For a typical home with 4-6 zones:

```yaml
Main Target When All Zones Satisfied: 50% (0.5)
Minimum Valves Open: 1
Main Change Threshold: 0.5°C
Valve Actuation Delay: 60s
Coordinator Interval: 15s
Satisfaction Epsilon: 0.1°C
Zone Opening Offset: 0.3°C
Zone Closing Offset: 0.3°C
```

## Safety Considerations

1. **Always maintain minimum valve requirement** to prevent HVAC system damage
2. **Monitor main climate limits** to prevent unsafe temperatures
3. **Set appropriate delays** to avoid valve wear
4. **Use fallback valves** in critical zones
5. **Test fail-safe behavior** by stopping Redis or Home Assistant

## Support

For issues and questions:
- GitHub Issues: https://github.com/Chester929/ha_multizone_climate/issues
- Discussions: https://github.com/Chester929/ha_multizone_climate/discussions
