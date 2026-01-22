# Configuration Guide

## Global Configuration

Access via: Settings → Devices & Services → Multizone Climate → Configure

### Main Target Calculation Mode

**Slider-based (default)**:
- Uses linear interpolation between min and max zone targets
- Slider position (0-100%) controls main target:
  - 0% = Lowest zone target (energy efficient)
  - 50% = Midpoint between min and max (balanced)
  - 100% = Highest zone target (faster response)

**Average mode**:
- Calculates arithmetic mean of all active zone targets
- Ignores slider setting
- More responsive to individual zone changes

### Minimum Valves Open

Number of valves that must remain open at all times for system safety.

**Important**: Configure at least this many zones as fallback valves.

- Default: 1
- Range: 1-10
- Recommendation: Set based on HVAC manufacturer specifications

### Main Temperature Limits

Temperature range for main climate thermostat.

- Min Temperature: Default 18.0°C
- Max Temperature: Default 30.0°C
- Adjust based on your HVAC unit capabilities

### Main Change Threshold

Minimum temperature change to update main climate.

- Default: 0.5°C
- Prevents excessive updates for tiny changes
- Reduces API calls to cloud-connected thermostats

### Valve Actuation Delay

Physical time for valve to fully open or close.

- Default: 120 seconds (2 minutes)
- Range: 60-300 seconds
- Set based on your valve motor specifications
- Used for cooldown period to prevent chattering

### Coordinator Interval

How often to check for pending jobs and update states.

- Default: 15 seconds
- Range: 10-60 seconds
- Lower = more responsive, higher CPU usage
- Higher = less responsive, lower CPU usage

### Satisfaction Epsilon

Buffer zone around target temperature for satisfaction determination.

- Default: 0.0°C (exact target)
- Range: 0.0-0.5°C
- Higher values prevent premature "satisfied" status during rapid temperature changes

## Zone Configuration

Each zone has individual parameters:

### Target Change Threshold

Step size for target temperature adjustments.

- Default: 0.1°C
- Determines slider/button increment in UI

### Opening Offset Below Target

Temperature below target to trigger valve opening.

- Default: 0.3°C
- Example: Target 21°C, offset 0.3°C → valve opens at 20.7°C

### Closing Offset Above Target

Temperature above target to trigger valve closing.

- Default: 0.3°C
- Example: Target 21°C, offset 0.3°C → valve closes at 21.3°C

### Is Fallback Valve

Mark zone as fallback for safety enforcement.

- When minimum valves not met, fallback valves are forced open
- Configure at least as many fallback zones as min_valves_open

### Priority

Zone priority for heating/cooling order.

- Default: 0
- Higher numbers = higher priority
- Zones with priority > 0 are managed before default priority zones
- Among equal priority, temperature deficit determines order

## Recommended Configurations

### Conservative (Safe, slower)

```yaml
min_valves_open: 2
valve_actuation_delay: 180
coordinator_interval: 30
opening_offset: 0.5
closing_offset: 0.5
satisfaction_eps: 0.2
```

### Balanced (Default)

```yaml
min_valves_open: 1
valve_actuation_delay: 120
coordinator_interval: 15
opening_offset: 0.3
closing_offset: 0.3
satisfaction_eps: 0.0
```

### Aggressive (Fast, more wear)

```yaml
min_valves_open: 1
valve_actuation_delay: 60
coordinator_interval: 10
opening_offset: 0.2
closing_offset: 0.2
satisfaction_eps: 0.0
```

## Next Steps

- [User Guide](user-guide.md) - Daily usage
- [Troubleshooting](troubleshooting.md) - Common issues
