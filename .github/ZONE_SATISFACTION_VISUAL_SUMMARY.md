# Zone Satisfaction State Refactoring - Visual Summary

## Quick Comparison

### BEFORE (Current Design)

```
┌─────────────────────────────────────────────────────────────┐
│  Temperature Sensor (sensor.bedroom_temp)                   │
│  Current: 20.5°C                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Zone Climate Entity (climate.bedroom)                      │
│  - Reads temperature from sensor                            │
│  - Stores target temperature                                │
│  - Writes to Redis: temp, target                            │
│  - Does NOT calculate satisfaction                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
              [Redis Storage]
         {temp: 20.5, target: 21.0}
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Coordinator (every 15s)                                    │
│  - Reads Redis                                              │
│  - Updates entity sensors                                   │
│  - Triggers Update Valves job                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Update Valves Job                                          │
│  1. Reads all zone data from Redis                          │
│  2. CALCULATES satisfaction for each zone ◄── COMPLEXITY!   │
│     - Checks bounds (opening/closing offsets)               │
│     - Applies hysteresis logic                              │
│     - Determines underheated/satisfied/overheated           │
│  3. Sorts zones by priority                                 │
│  4. Determines valve actions                                │
│  5. Updates Redis with satisfaction states                  │
│  6. Controls physical valves                                │
└─────────────────────────────────────────────────────────────┘

⚠️ ISSUES:
- Separation of concerns: Job does too much
- Delayed updates: Satisfaction calculated every 15s
- Redundant reads: Job reads all data to calculate
- Entity doesn't know its own satisfaction state
```

### AFTER (Proposed Design)

```
┌─────────────────────────────────────────────────────────────┐
│  Temperature Sensor (sensor.bedroom_temp)                   │
│  Current: 20.5°C                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Zone Climate Entity (climate.bedroom) ◄── ENHANCED!        │
│  1. Reads temperature from sensor                           │
│  2. Stores target temperature                               │
│  3. CALCULATES satisfaction state ◄── MOVED HERE!           │
│     - Checks bounds (opening/closing offsets)               │
│     - Applies hysteresis logic                              │
│     - Determines underheated/satisfied/overheated           │
│  4. Determines temperature direction (rising/falling)       │
│  5. Writes to Redis: temp, target, satisfaction, direction  │
│  6. Updates entity attributes immediately                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
              [Redis Storage]
    {temp: 20.5, target: 21.0, 
     satisfaction: "underheated",
     rising: true, falling: false}
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Binary Sensors (NEW!)                                      │
│  - binary_sensor.bedroom_temperature_rising = ON            │
│  - binary_sensor.bedroom_temperature_falling = OFF          │
│  - binary_sensor.bedroom_temperature_stable = OFF           │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Coordinator (every 15s)                                    │
│  - Reads Redis                                              │
│  - Updates sensor entities                                  │
│  - Triggers Update Valves job                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Update Valves Job ◄── SIMPLIFIED!                          │
│  1. Reads all zone data from Redis                          │
│  2. Satisfaction already calculated by entities ◄── FASTER! │
│  3. Sorts zones by priority                                 │
│  4. Determines valve actions                                │
│  5. Controls physical valves                                │
└─────────────────────────────────────────────────────────────┘

✅ BENEFITS:
- Clear separation: Entities know their own state
- Real-time updates: Satisfaction updates immediately
- Simplified job: Less code, less complexity
- Better UX: Users see live satisfaction status
- Extensible: Easy to add more zone-level sensors
```

## Side-by-Side Code Comparison

### Update Valves Job - Before

```python
def update_valves(zones, config, main_climate_state, multizone_enabled):
    # 65+ LINES OF SATISFACTION CALCULATION CODE
    for zone in zones:
        if zone.state == "OFF":
            zone.satisfaction = "off"
            continue
        
        prev_satisfaction = zone.satisfaction if hasattr(zone, 'satisfaction') else None
        
        if main_climate_state == "HEATING":
            if zone.current_temp < (zone.target_temp - config.opening_offset):
                zone.satisfaction = "underheated"
            elif zone.current_temp > (zone.target_temp + config.closing_offset):
                zone.satisfaction = "overheated"
            else:
                # 30+ lines of hysteresis logic
                if prev_satisfaction == "underheated":
                    if zone.current_temp >= (zone.target_temp + config.satisfaction_eps):
                        zone.satisfaction = "satisfied"
                    else:
                        zone.satisfaction = "underheated"
                # ... more logic
        else:  # COOLING
            # 30+ more lines for cooling mode
            # ...
    
    # Calculate sort key
    # ... rest of algorithm
```

**Lines of code**: ~65 lines for satisfaction + 50 lines for valve logic = **115 lines**

### Update Valves Job - After

```python
def update_valves(zones, config, main_climate_state, multizone_enabled):
    # Fetch zone states from Redis (includes pre-calculated satisfaction)
    zone_states = await fetch_zones_from_redis(zones)
    
    # Satisfaction already set by entities!
    # zone.satisfaction is already "underheated", "satisfied", "overheated", etc.
    
    # Calculate sort key (user priority + temperature deficit)
    for zone in zone_states:
        if zone.state == "OFF":
            zone.sort_key = (-1000, -1000)
        elif main_climate_state == "HEATING":
            deficit = zone.target_temp - zone.current_temp
            zone.sort_key = (zone.priority, deficit)
        else:  # COOLING
            deficit = zone.current_temp - zone.target_temp
            zone.sort_key = (zone.priority, deficit)
    
    # ... rest of algorithm (sorting, valve actions, safety checks)
```

**Lines of code**: ~10 lines for sort key + 50 lines for valve logic = **60 lines**

**Reduction**: **55 lines removed** (~47% reduction in complexity)

## Zone Entity - Before vs After

### Zone Entity Attributes - Before

```python
{
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "hvac_mode": "heat",
  "hvac_action": "heating"
}
```

**Missing**: satisfaction, temperature direction

### Zone Entity Attributes - After

```python
{
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "hvac_mode": "heat",
  "hvac_action": "heating",
  "satisfaction": "underheated",        # ◄── NEW!
  "temperature_rising": true,           # ◄── NEW!
  "temperature_falling": false,         # ◄── NEW!
  "temperature_stable": false,          # ◄── NEW!
  "valve_state": "open",
  "priority": 0
}
```

**Added**: 4 new attributes that provide real-time zone status

## Redis Schema Changes

### Zone State in Redis - Before

```json
{
  "id": "zone_bedroom",
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "state": "ON",
  "satisfaction": "underheated",
  "valve_state": "open"
}
```

**Updated by**: Update Valves job (every 15s via coordinator)

### Zone State in Redis - After

```json
{
  "id": "zone_bedroom",
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "state": "ON",
  "satisfaction": "underheated",
  "valve_state": "open",
  "temperature_rising": true,        // ◄── NEW!
  "temperature_falling": false,      // ◄── NEW!
  "temperature_stable": false,       // ◄── NEW!
  "last_updated": "2026-01-14T18:45:23Z"
}
```

**Updated by**: Zone entity itself (immediately on temperature change)

## User Experience Impact

### Dashboard View - Before

```
┌─────────────────────────────────┐
│  Bedroom Climate                │
│  Current: 20.5°C                │
│  Target: 21.0°C                 │
│  Valve: Open                    │
│                                 │
│  ❓ Satisfaction: Unknown       │
│     (updated every 15s)         │
└─────────────────────────────────┘
```

**User sees**: Basic info only, satisfaction delayed

### Dashboard View - After

```
┌─────────────────────────────────┐
│  Bedroom Climate                │
│  Current: 20.5°C ↗ Rising       │  ◄── NEW!
│  Target: 21.0°C                 │
│  Valve: Open                    │
│                                 │
│  🔥 Underheated                 │  ◄── REAL-TIME!
│     (needs heating)             │
│                                 │
│  Binary Sensors:                │  ◄── NEW!
│  🟢 Temperature Rising          │
│  ⚫ Temperature Falling          │
│  ⚫ Temperature Stable           │
└─────────────────────────────────┘
```

**User sees**: Complete real-time status with direction indicators

## Automation Examples

### What Users Can Do - Before

Limited automation capabilities:
```yaml
# User can only react to temperature thresholds
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.bedroom_temperature
        below: 20.5
    action:
      # Do something when cold
```

### What Users Can Do - After

Rich automation capabilities:
```yaml
# Example 1: React to satisfaction state
automation:
  - trigger:
      - platform: state
        entity_id: climate.bedroom
        attribute: satisfaction
        to: "underheated"
    action:
      - service: notify.mobile_app
        data:
          message: "Bedroom is underheated!"

# Example 2: React to temperature direction
automation:
  - trigger:
      - platform: state
        entity_id: binary_sensor.bedroom_temperature_falling
        to: "on"
    condition:
      - condition: state
        entity_id: climate.bedroom
        attribute: satisfaction
        state: "satisfied"
    action:
      - service: notify.mobile_app
        data:
          message: "Bedroom temperature dropping, might need heat soon"

# Example 3: Detect rapid temperature changes
automation:
  - trigger:
      - platform: state
        entity_id: binary_sensor.bedroom_temperature_rising
        to: "on"
        for: "00:00:30"
    action:
      # Detect if temperature is rising for 30s straight
      # Could indicate window opened or HVAC issue
```

## Performance Impact

### Redis Operations - Before

```
Temperature Change Event:
  ├─ Zone entity → Redis: Write (temp, target) = 1 write
  └─ Coordinator (15s later):
      ├─ Read all zones = 1 read per zone
      ├─ Update Valves job:
      │   ├─ Read all zones again = 1 read per zone
      │   ├─ Calculate satisfaction (CPU intensive)
      │   └─ Write satisfaction = 1 write per zone
      └─ Total: 2 reads + 1 write per zone (delayed)
```

**Delay**: Up to 15 seconds for satisfaction update

### Redis Operations - After

```
Temperature Change Event:
  └─ Zone entity → Redis: Write (temp, target, satisfaction, direction) = 1 write
  
Update Valves job:
  ├─ Read all zones = 1 read per zone
  └─ Use pre-calculated satisfaction (no CPU work)
  
Total: 1 immediate write, 1 read (when job runs)
```

**Delay**: Immediate satisfaction update (0 seconds)

**Performance Impact**:
- ✅ Fewer Redis reads per update cycle
- ✅ Less CPU work (no recalculation)
- ⚠️ Slightly more Redis writes (but immediate and debounced)
- ✅ Overall: Better performance and responsiveness

## Migration Path

### Step 1: Add New Logic (No Breaking Changes)

```python
class MultizoneClimateZoneEntity(ClimateEntity):
    def __init__(self, ..., use_entity_satisfaction=False):
        self._use_entity_satisfaction = use_entity_satisfaction  # Feature flag
        
    async def async_update(self):
        if self._use_entity_satisfaction:
            # New logic: Calculate satisfaction here
            self._calculate_satisfaction_state()
            await self._write_state_to_redis()
        else:
            # Old logic: Just write temp/target
            await self._write_basic_state_to_redis()
```

### Step 2: Enable Feature Flag

```yaml
# Configuration option
multizone_climate:
  use_entity_satisfaction: true  # Enable new behavior
```

### Step 3: Remove Old Logic

Once tested and stable, remove feature flag and old code paths.

## Summary

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| **Satisfaction Calculation** | Update Valves Job | Zone Entity | ✅ Better separation |
| **Update Frequency** | Every 15s (coordinator) | Immediate | ✅ Real-time |
| **Lines of Code** | 115 lines | 60 lines | ✅ 47% reduction |
| **Entity Attributes** | 4 attributes | 8 attributes | ✅ Richer data |
| **Binary Sensors** | 0 | 3 per zone | ✅ New features |
| **Redis Writes** | Delayed | Immediate | ⚠️ Slightly more |
| **User Automations** | Limited | Rich | ✅ Better UX |
| **Code Maintainability** | Complex job | Simple job | ✅ Easier to maintain |

## Conclusion

The proposed refactoring:

✅ **Aligns with documented architecture** (README.md line 185)  
✅ **Reduces code complexity** (47% fewer lines in Update Valves job)  
✅ **Improves user experience** (real-time status updates)  
✅ **Enables new features** (rising/falling sensors)  
✅ **Better separation of concerns** (entities manage their own state)  
✅ **Low risk** (additive changes, backward compatible during migration)  

**Recommendation**: Proceed with implementation after clarifying 5 key questions in the main proposal document.
