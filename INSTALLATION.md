# Installation Guide

This guide covers both installation methods for the Multizone Climate integration.

## Table of Contents
1. [Method 1: Home Assistant Add-on](#method-1-home-assistant-add-on-recommended)
2. [Method 2: HACS Custom Integration](#method-2-hacs-custom-integration)
3. [Configuration](#configuration)
4. [Adding Zones](#adding-zones)
5. [Troubleshooting](#troubleshooting)

---

## Method 1: Home Assistant Add-on (Recommended)

The add-on provides a complete solution with Redis included.

### Prerequisites
- Home Assistant OS, Supervised, or Container installation
- Supported architecture: amd64, armv7, aarch64, or i386

### Installation Steps

1. **Add Repository to Add-on Store**
   - Open Home Assistant
   - Navigate to **Settings → Add-ons → Add-on Store**
   - Click the menu (⋮) in the top right
   - Select **Repositories**
   - Add: `https://github.com/Chester929/ha_multizone_climate`

2. **Install the Add-on**
   - Find "Multizone Climate" in the add-on store
   - Click on it and click **Install**
   - Wait for installation to complete

3. **Configure the Add-on**
   - Go to the **Configuration** tab
   - Review and adjust settings:
     ```yaml
     redis_host: "localhost"
     redis_port: 6379
     redis_password: ""        # Optional
     redis_db: 0
     redis_key_prefix: "ha_multizone"
     install_integration: true  # Auto-install the integration
     log_level: "info"
     ```
   - Click **Save**

4. **Start the Add-on**
   - Go to the **Info** tab
   - Click **Start**
   - Optionally enable **Start on boot** and **Watchdog**
   - Check the **Log** tab to verify Redis started successfully

5. **Restart Home Assistant**
   - Navigate to **Settings → System → Restart**
   - Click **Restart Home Assistant**
   - Wait for restart to complete

6. **Configure the Integration**
   - Navigate to **Settings → Devices & Services**
   - Click **+ Add Integration**
   - Search for "Multizone Climate"
   - Click on it to start configuration
   - Follow the configuration wizard (see [Configuration](#configuration) section)

---

## Method 2: HACS Custom Integration

Install just the integration if you have your own Redis server.

### Prerequisites
- Home Assistant (any installation type)
- Redis server 4.5+ running and accessible
- HACS installed (recommended) OR manual installation capability

### Option A: Install via HACS

1. **Add Custom Repository**
   - Open HACS in Home Assistant
   - Click on **Integrations**
   - Click the menu (⋮) in the top right
   - Select **Custom repositories**
   - Add repository: `https://github.com/Chester929/ha_multizone_climate`
   - Category: **Integration**
   - Click **Add**

2. **Install the Integration**
   - Find "Multizone Climate" in HACS
   - Click **Download**
   - Click **Download** again to confirm
   - Restart Home Assistant

3. **Add the Integration**
   - Navigate to **Settings → Devices & Services**
   - Click **+ Add Integration**
   - Search for "Multizone Climate"
   - Follow the configuration wizard

### Option B: Manual Installation

1. **Download the Integration**
   ```bash
   cd /config/custom_components
   git clone https://github.com/Chester929/ha_multizone_climate.git
   cp -r ha_multizone_climate/multizone_climate/custom_components/multizone_climate .
   ```

2. **Restart Home Assistant**

3. **Add the Integration**
   - Same as Option A step 3

### Redis Setup (for Manual Method)

You need to provide your own Redis instance. Options include:

**Option 1: Docker**
```bash
docker run -d \
  --name redis-multizone \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
```

**Option 2: System Package**
```bash
# Debian/Ubuntu
sudo apt-get install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**Option 3: Another Add-on**
- Install the "Redis" add-on from the official add-on store
- Configure it and start it

---

## Configuration

### Initial Setup Wizard

After adding the integration, you'll go through a multi-step configuration:

#### Step 1: Redis Connection

Configure the Redis server connection.

| Field | Description | Default | Required |
|-------|-------------|---------|----------|
| Redis Host | Hostname or IP of Redis server | localhost | Yes |
| Redis Port | Port number | 6379 | Yes |
| Redis Password | Authentication password | (empty) | No |
| Redis Database | Database number (0-15) | 0 | Yes |
| Redis Key Prefix | Prefix for all keys | ha_multizone | Yes |

**For Add-on Users:** Use the defaults (localhost:6379) as the add-on provides Redis.

**For Manual Users:** Enter your Redis server details.

#### Step 2: Main Climate Configuration

Configure the main HVAC thermostat and automation settings.

| Field | Description | Default | Range |
|-------|-------------|---------|-------|
| Main Climate Entity | Your main HVAC thermostat | - | Required |
| Use Average Mode | Use average instead of slider | No | - |
| Main Target (Slider) | Target when all satisfied (0-100%) | 50% | 0-100% |
| Minimum Valves Open | Safety minimum | 1 | ≥1 |
| Main Min Temperature | Minimum main temp | 18.0°C | 10-35°C |
| Main Max Temperature | Maximum main temp | 30.0°C | 10-35°C |
| Main Change Threshold | Minimum change to update | 0.5°C | 0.1-2.0°C |
| Valve Actuation Delay | Physical valve delay | 120s | 30-300s |
| Coordinator Interval | Update frequency | 15s | 5-60s |
| Satisfaction Epsilon | Satisfaction buffer | 0.0°C | 0.0-1.0°C |

**Tips:**
- **Main Climate Entity**: Select the climate entity for your main thermostat
- **Slider vs Average**: 
  - Slider: More control, interpolates between min/max zone targets
  - Average: Simpler, uses arithmetic mean of all zones
- **Minimum Valves Open**: Must match number of fallback valves (set when adding zones)
- **Valve Actuation Delay**: Time for physical valve to fully open/close (usually 60-180s)

---

## Adding Zones

After initial setup, add climate zones for each room.

### Add Zone via UI

1. Navigate to **Settings → Devices & Services**
2. Find "Multizone Climate" integration
3. Click **Configure** (or the integration name)
4. Click **Add Zone** (if available) OR use the service call method below

### Add Zone via Service Call

If UI method is not available yet, use a service call:

1. Go to **Developer Tools → Services**
2. Select service: `multizone_climate.add_zone`
3. Configure the zone:

```yaml
service: multizone_climate.add_zone
data:
  zone_name: "Bedroom"
  temperature_sensor_entity_id: "sensor.bedroom_temperature"
  valve_switch_entity_id: "switch.bedroom_valve"
  target_change_threshold: 0.1
  opening_offset: 0.3
  closing_offset: 0.3
  is_fallback_valve: true
  priority: 0
```

### Zone Configuration Parameters

| Field | Description | Default | Notes |
|-------|-------------|---------|-------|
| Zone Name | Display name | - | Required |
| Temperature Sensor | Entity ID of temp sensor | - | Required |
| Valve Switch | Entity ID of valve switch | - | Required |
| Target Change Threshold | Minimum target change | 0.1°C | For UI updates |
| Opening Offset | Temp below target to open | 0.3°C | Creates hysteresis |
| Closing Offset | Temp above target to close | 0.3°C | Prevents chattering |
| Is Fallback Valve | Safety fallback valve | false | One per zone minimum |
| Priority | Zone priority (higher first) | 0 | 0 = use deficit sort |

**Important:**
- **Fallback Valves**: Mark at least N zones as fallback (where N = Minimum Valves Open)
- **Priority**: Higher numbers get heating/cooling first. Priority 0 uses temperature deficit.
- **Offsets**: Larger values = more hysteresis = less valve cycling

---

## Enabling Multizone Feature

Once you have at least one zone configured:

1. Find the multizone enable switch entity
2. Turn it **ON** to activate automated zone management
3. Monitor the system through sensors and logs

**When ON:**
- System automatically manages all zone valves
- Main thermostat target is calculated based on zone needs
- Safety checks ensure minimum valves stay open

**When OFF:**
- Each zone manages its own valve independently
- No coordinated temperature calculation
- Safety checks still run

---

## Troubleshooting

### Add-on Issues

**Redis won't start**
- Check add-on logs: **Add-ons → Multizone Climate → Log**
- Verify port 6379 is not in use by another service
- Try changing `redis_port` in add-on config

**Integration not appearing**
- Ensure `install_integration: true` in add-on config
- Check add-on logs for installation messages
- Manually copy files from `/addon_configs/[addon-id]/custom_components`
- Restart Home Assistant

### Integration Issues

**Can't connect to Redis**
- For add-on: Ensure add-on is running
- For manual: Verify Redis is accessible at configured host:port
- Test connection: `redis-cli -h HOST -p PORT ping`

**Main thermostat not updating**
- Check `main_change_threshold` - may be too large
- Verify main climate entity is correct
- Check zone temperatures are different enough to trigger change

**Valves not responding**
- Enable multizone feature (switch must be ON)
- Verify zone entities exist and are configured
- Check valve switch entities are working manually
- Review `valve_actuation_delay` - may need adjustment

**All valves closed (safety violation)**
- Check `min_valves_open` setting
- Ensure enough zones marked as `is_fallback_valve: true`
- Review safety check logs

### Getting Help

- **Logs**: Check Home Assistant logs and add-on logs
- **Debug Mode**: Set `log_level: debug` in add-on config
- **Issues**: Report at https://github.com/Chester929/ha_multizone_climate/issues
- **Documentation**: See README.md and DIAGRAMS.md for detailed system info

---

## Next Steps

After installation:

1. **Test Basic Functionality**
   - Add one zone
   - Enable multizone
   - Monitor temperature and valve changes

2. **Add More Zones**
   - Configure all rooms
   - Set priorities if needed
   - Mark fallback valves

3. **Optimize Settings**
   - Adjust offsets for your system
   - Tune actuation delays
   - Fine-tune temperature thresholds

4. **Create Dashboards**
   - Use built-in entities in Lovelace
   - Monitor zone satisfaction states
   - Track valve operations

5. **Advanced Configuration**
   - Adjust satisfaction epsilon
   - Experiment with slider vs average mode
   - Set zone priorities based on usage
