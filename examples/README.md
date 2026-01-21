# Examples

This directory contains example configurations and scripts for the Multizone Climate system.

## Files

### docker-compose.ghcr.yml (Root Directory)

Example docker-compose file that uses pre-built multi-architecture images from GitHub Container Registry (GHCR). This is located in the root directory and is useful for:
- Quick deployment without building images locally
- Using tested, released versions
- Automatic architecture detection (amd64, armv7, aarch64)

To use pre-built images:

```bash
# From the root directory
cp .env.example .env
# Edit .env with your settings

# Start services using pre-built images
docker-compose -f docker-compose.ghcr.yml up -d
```

### zones-config.yaml

Example zone configuration in YAML format. This demonstrates:
- Global system configuration
- Multiple zone configurations (bedroom, living room, kitchen, bathroom)
- Entity mappings for temperature sensors and valve switches

### init-redis.sh

Shell script to initialize Redis with example data. This script:
- Sets global configuration
- Creates example zones
- Initializes zone states
- Sets main climate state

## Usage

### Initialize Redis with Example Data

After starting the containers with `docker-compose up -d`, run:

```bash
./examples/init-redis.sh
```

Or if Redis requires authentication:

```bash
REDIS_PASSWORD=your_password ./examples/init-redis.sh
```

### Custom Redis Host/Port

```bash
REDIS_HOST=custom_host REDIS_PORT=6380 ./examples/init-redis.sh
```

### Verify Configuration

After initialization, you can verify the configuration:

```bash
# View global config
redis-cli HGETALL multizone:config

# View zones list
redis-cli LRANGE multizone:zones 0 -1

# View specific zone
redis-cli HGETALL multizone:zone:bedroom

# View all zone keys
redis-cli KEYS "multizone:zone:*"
```

### Access the Add-on API

After initialization, the add-on API is available at:
- http://localhost:8080 (when using docker-compose)
- Or via Home Assistant: `http://addon_slug:8080` (when using the add-on)

You can query the API to see the example zones and their states.

### Access via Custom Integration

When using the Home Assistant add-on:
1. Install the custom integration
2. Configure zones through the integration wizard
3. The integration will create climate entities for each zone

## Customizing the Configuration

1. **Edit zones-config.yaml** with your zone names and entity IDs
2. **Modify init-redis.sh** to match your configuration
3. **Run the script** to apply your changes

## Integration with Home Assistant

Make sure your Home Assistant has entities matching the configured IDs:
- `sensor.bedroom_temperature`
- `switch.bedroom_valve`
- `sensor.living_room_temperature`
- `switch.living_room_valve`
- etc.

## Resetting Configuration

To reset and reinitialize:

```bash
# Clear all multizone keys
redis-cli --scan --pattern "multizone:*" | xargs redis-cli DEL

# Reinitialize
./examples/init-redis.sh
```
