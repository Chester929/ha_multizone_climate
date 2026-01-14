# Zone Satisfaction State Refactoring - Analysis & Proposal

## Executive Summary

**Current State**: Zone satisfaction states (underheated/overheated/satisfied) are calculated in the "Update Valves" background job.

**Proposed Change**: Move satisfaction state calculation into each Climate Zone Entity, allowing entities to self-manage their states and write them to Redis.

**Status**: ✅ **RECOMMENDED** - This refactoring aligns with the documented architecture and provides significant benefits.

---

## Current Architecture Analysis

### Documentation Review

From **README.md Line 185**:
> "These zone climate entities control target temperature, but they do not control valves. They only provide information about current temperature, target temperature, and **satisfaction status** in the zone."

This clearly indicates that **zone climate entities should provide satisfaction status**, but the current algorithm design has this calculation happening in the Update Valves job (lines 536-600).

### Current Flow (As Documented)

```
Temperature Sensor → Zone Entity → Update Valves Job
                         ↓              ↓
                    Redis (temp)   Calculates Satisfaction
                                        ↓
                                   Updates Redis (satisfaction)
                                        ↓
                                   Determines Valve Actions
```

### Issues with Current Design

1. **Separation of Concerns**: Zone entities should know their own satisfaction state
2. **Redundant Reads**: Update Valves job must read all zone data from Redis to calculate states
3. **Delayed State Updates**: Satisfaction states only update when Update Valves job runs (every 15s via coordinator)
4. **Coordinator Overhead**: Entity state updates happen in coordinator (line 96-97) but satisfaction is calculated elsewhere
5. **Inconsistent with Entity Model**: Home Assistant entities should manage their own state

---

## Proposed Architecture

### New Flow

```
Temperature Sensor → Zone Entity
                         ↓
                    Calculate Satisfaction State
                         ↓
                    Write to Redis
                         ↓
                    Update Entity State
                         
Update Valves Job → Read Satisfaction from Redis
                         ↓
                    Determine Valve Actions
```

### What Changes

#### 1. Climate Zone Entity Enhancement

Each climate zone entity will:
- Calculate its own satisfaction state when temperature or target changes
- Track previous satisfaction state (for hysteresis)
- Determine temperature direction (rising/falling)
- Write satisfaction state to Redis immediately
- Expose satisfaction state as entity attribute/sensor

#### 2. Rising/Falling Sensors (NEW)

Add temperature direction tracking to each zone:
- **Binary Sensor: `{zone}_temperature_rising`** - True when temperature is increasing
- **Binary Sensor: `{zone}_temperature_falling`** - True when temperature is decreasing
- **Binary Sensor: `{zone}_temperature_stable`** - True when temperature is stable

Implementation:
- Compare current temperature with previous temperature (from last 30-60 seconds)
- Use configurable threshold (e.g., 0.05°C change to consider movement)
- Helps understand zone thermal behavior

#### 3. Update Valves Job Simplification

The Update Valves job becomes simpler:
```python
def update_valves(zones, config, main_climate_state, multizone_enabled):
    # Satisfaction states already calculated by entities
    # Just read from Redis
    
    for zone in zones:
        # zone.satisfaction already set by entity
        # No need to calculate here
        pass
    
    # Continue with priority sorting and valve logic
    # ... rest of algorithm unchanged
```

#### 4. Coordinator Changes

The coordinator currently "Updates entity states" (line 97). With this change:
- Zone entities update their own satisfaction states immediately
- Coordinator still reads from Redis to update sensor entities
- Coordinator no longer needs to calculate satisfaction

---

## Detailed Implementation Plan

### Phase 1: Climate Zone Entity Enhancement

**File**: `custom_components/ha_multizone_climate/climate.py` (to be created)

```python
class MultizoneClimateZoneEntity(ClimateEntity):
    """Climate entity for individual zone."""
    
    def __init__(self, ...):
        self._prev_temperature = None
        self._prev_satisfaction = None
        self._temperature_history = []  # For rising/falling detection
        
    @property
    def extra_state_attributes(self):
        """Return entity attributes."""
        return {
            "satisfaction": self._satisfaction,
            "temperature_rising": self._temperature_rising,
            "temperature_falling": self._temperature_falling,
            "temperature_stable": self._temperature_stable,
            "valve_state": self._valve_state,
            "priority": self._priority,
        }
    
    async def async_update(self):
        """Update zone state from temperature sensor."""
        # Read current temperature from sensor
        current_temp = self._get_current_temperature()
        
        # Determine temperature direction
        self._update_temperature_direction(current_temp)
        
        # Calculate satisfaction state
        self._calculate_satisfaction_state(current_temp)
        
        # Write to Redis
        await self._write_state_to_redis()
        
    def _update_temperature_direction(self, current_temp):
        """Determine if temperature is rising, falling, or stable."""
        if self._prev_temperature is None:
            self._temperature_rising = False
            self._temperature_falling = False
            self._temperature_stable = True
            self._prev_temperature = current_temp
            return
        
        # Add to history (keep last 3-5 readings for smoothing)
        self._temperature_history.append(current_temp)
        if len(self._temperature_history) > 5:
            self._temperature_history.pop(0)
        
        # Calculate trend (simple: compare current with average of history)
        if len(self._temperature_history) >= 2:
            avg_prev = sum(self._temperature_history[:-1]) / len(self._temperature_history[:-1])
            delta = current_temp - avg_prev
            
            threshold = 0.05  # 0.05°C threshold for direction detection
            
            if delta > threshold:
                self._temperature_rising = True
                self._temperature_falling = False
                self._temperature_stable = False
            elif delta < -threshold:
                self._temperature_rising = False
                self._temperature_falling = True
                self._temperature_stable = False
            else:
                self._temperature_rising = False
                self._temperature_falling = False
                self._temperature_stable = True
        
        self._prev_temperature = current_temp
    
    def _calculate_satisfaction_state(self, current_temp):
        """Calculate zone satisfaction state with hysteresis."""
        # This is the logic currently in Update Valves (lines 536-600)
        # Moved here to the entity
        
        if self.state == "OFF":
            self._satisfaction = "off"
            return
        
        prev_satisfaction = self._prev_satisfaction or "unknown"
        target_temp = self._target_temperature
        
        # Get config from Redis
        config = self._get_config()
        main_climate_state = self._get_main_climate_state()
        
        if main_climate_state == "HEATING":
            # Heating mode satisfaction logic
            if current_temp < (target_temp - config.opening_offset):
                self._satisfaction = "underheated"
            elif current_temp > (target_temp + config.closing_offset):
                self._satisfaction = "overheated"
            else:
                # Within hysteresis band - check transitions
                if prev_satisfaction == "underheated":
                    if current_temp >= (target_temp + config.satisfaction_eps):
                        self._satisfaction = "satisfied"
                    else:
                        self._satisfaction = "underheated"
                elif prev_satisfaction == "overheated":
                    if current_temp <= (target_temp - config.satisfaction_eps):
                        self._satisfaction = "satisfied"
                    else:
                        self._satisfaction = "overheated"
                else:
                    self._satisfaction = "satisfied"
        else:  # COOLING
            # Cooling mode satisfaction logic
            if current_temp > (target_temp + config.opening_offset):
                self._satisfaction = "undercooled"
            elif current_temp < (target_temp - config.closing_offset):
                self._satisfaction = "overcooled"
            else:
                # Within hysteresis band - check transitions
                if prev_satisfaction == "undercooled":
                    if current_temp <= (target_temp - config.satisfaction_eps):
                        self._satisfaction = "satisfied"
                    else:
                        self._satisfaction = "undercooled"
                elif prev_satisfaction == "overcooled":
                    if current_temp >= (target_temp + config.satisfaction_eps):
                        self._satisfaction = "satisfied"
                    else:
                        self._satisfaction = "overcooled"
                else:
                    self._satisfaction = "satisfied"
        
        # Save previous state for next iteration
        self._prev_satisfaction = self._satisfaction
    
    async def _write_state_to_redis(self):
        """Write zone state to Redis."""
        zone_data = {
            "id": self._zone_id,
            "current_temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "state": self.state,
            "satisfaction": self._satisfaction,
            "valve_state": self._valve_state,
            "temperature_rising": self._temperature_rising,
            "temperature_falling": self._temperature_falling,
            "temperature_stable": self._temperature_stable,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        
        await self._redis_client.hset(
            f"ha_multizone:zone:{self._zone_id}",
            mapping=zone_data
        )
```

### Phase 2: Binary Sensors for Temperature Direction

**File**: `custom_components/ha_multizone_climate/binary_sensor.py` (to be created)

```python
class ZoneTemperatureDirectionSensor(BinarySensorEntity):
    """Binary sensor for temperature direction (rising/falling/stable)."""
    
    def __init__(self, zone_entity, direction_type):
        """Initialize sensor.
        
        Args:
            zone_entity: Parent zone climate entity
            direction_type: "rising", "falling", or "stable"
        """
        self._zone_entity = zone_entity
        self._direction_type = direction_type
        
    @property
    def is_on(self):
        """Return True if temperature is moving in this direction."""
        if self._direction_type == "rising":
            return self._zone_entity._temperature_rising
        elif self._direction_type == "falling":
            return self._zone_entity._temperature_falling
        else:  # stable
            return self._zone_entity._temperature_stable
```

### Phase 3: Update Valves Job Refactoring

**File**: `custom_components/ha_multizone_climate/jobs/update_valves.py` (to be created)

Remove satisfaction calculation logic (lines 536-600), replace with:

```python
async def update_valves(zones, config, main_climate_state, multizone_enabled):
    """Update valve states based on zone temperatures and satisfaction.
    
    Satisfaction states are now read from Redis (calculated by zone entities).
    """
    
    # Fetch zone states from Redis (includes pre-calculated satisfaction)
    zone_states = await fetch_zones_from_redis(zones)
    
    # Satisfaction already set by entities
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
    
    # ... rest of algorithm unchanged (sorting, valve actions, safety checks)
```

### Phase 4: Redis Schema Update

**Update**: `ha_multizone:zone:{zone_id}` Hash

Add new fields:
```json
{
  "id": "zone_bedroom",
  "name": "Bedroom",
  "temperature_sensor_entity_id": "sensor.bedroom_temperature",
  "valve_switch_entity_id": "switch.bedroom_valve",
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "state": "ON",
  "satisfaction": "underheated",
  "valve_state": "open",
  "temperature_rising": true,      // NEW
  "temperature_falling": false,    // NEW
  "temperature_stable": false,     // NEW
  "target_change_threshold": 0.1,
  "opening_offset": 0.3,
  "closing_offset": 0.3,
  "is_fallback_valve": false,
  "priority": 0,
  "last_updated": "2026-01-13T13:30:00Z"
}
```

---

## Benefits of This Approach

### 1. Separation of Concerns
- **Zone entities**: Manage their own state (temperature, satisfaction, direction)
- **Update Valves job**: Focuses on valve coordination and safety rules
- **Calculate Main Target job**: Focuses on main climate target calculation

### 2. Real-Time State Updates
- Satisfaction state updates immediately when temperature changes
- No need to wait for coordinator cycle (15s)
- More responsive to temperature changes

### 3. Simplified Update Valves Job
- No need to recalculate satisfaction states
- Just read pre-calculated states from Redis
- Reduced complexity and processing time

### 4. Better Home Assistant Integration
- Zone entities expose complete state through attributes
- Rising/falling sensors can be used in automations
- Users can monitor satisfaction status in real-time

### 5. Debugging and Monitoring
- Each zone's satisfaction state visible in entity attributes
- Temperature direction visible as binary sensors
- Easier to understand system behavior

### 6. Extensibility
- Easy to add more zone-level sensors (e.g., temperature rate of change)
- Zone entities can implement additional logic (predictive heating)
- Better foundation for future features

---

## Compatibility with Existing Design

### What Stays the Same

1. **Satisfaction State Machine**: Hysteresis logic remains identical (lines 536-600 logic moved, not changed)
2. **Update Valves Algorithm**: Priority sorting, safety checks, valve coordination unchanged
3. **Calculate Main Target**: No changes needed
4. **Redis Schema**: Only adds new fields, doesn't break existing structure
5. **Background Jobs**: Queue management and job locking unchanged
6. **Coordinator**: Still runs every 15s, still updates sensors

### What Changes

1. **Zone Entity Responsibility**: Now calculates own satisfaction state
2. **Update Valves Job**: Reads satisfaction from Redis instead of calculating
3. **New Sensors**: Rising/falling/stable binary sensors per zone
4. **Redis Writes**: Zone entities write directly to Redis

---

## Implementation Checklist

### Phase 1: Foundation (No Breaking Changes)
- [ ] Create Climate Zone Entity class with satisfaction calculation
- [ ] Implement temperature direction tracking
- [ ] Add Redis write logic to zone entity
- [ ] Ensure backward compatibility (both old and new logic work)

### Phase 2: Sensors (Additive)
- [ ] Create binary sensor platform for temperature direction
- [ ] Register sensors in config entry setup
- [ ] Test sensor state updates

### Phase 3: Refactor Update Valves (Cleanup)
- [ ] Remove satisfaction calculation from Update Valves job
- [ ] Update job to read satisfaction from Redis
- [ ] Test valve coordination still works correctly

### Phase 4: Documentation
- [ ] Update README.md algorithm section
- [ ] Update DIAGRAMS.md with new flow
- [ ] Add migration guide for existing installations

### Phase 5: Testing
- [ ] Unit tests for satisfaction state calculation in entity
- [ ] Integration tests for zone entity state updates
- [ ] Test Update Valves with pre-calculated satisfaction
- [ ] Test rising/falling sensor accuracy

---

## Risk Assessment

### Low Risk
- ✅ Additive changes (new sensors don't break existing functionality)
- ✅ Satisfaction logic moves but doesn't change
- ✅ Update Valves job simplified (less code = fewer bugs)

### Medium Risk
- ⚠️ Timing changes: Satisfaction updates immediately vs. every 15s
  - **Mitigation**: May need debouncing to prevent rapid state changes
- ⚠️ Increased Redis writes: Each zone writes on temperature change
  - **Mitigation**: Redis is fast, writes are small, use debouncing

### High Risk
- ❌ None identified

---

## Alternatives Considered

### Alternative 1: Keep Status Quo
**Pros**: No changes needed, well-documented
**Cons**: Misalignment with entity model, delayed updates, complex Update Valves job

### Alternative 2: Hybrid Approach
Calculate satisfaction in both places (entity for display, job for decisions)
**Pros**: Redundancy
**Cons**: Duplicate logic, potential inconsistencies, more maintenance

### Alternative 3: Proposed Approach (RECOMMENDED)
**Pros**: Clean separation, real-time updates, simpler code
**Cons**: Requires refactoring, increased Redis writes

---

## Recommendation

✅ **PROCEED WITH PROPOSED REFACTORING**

**Reasons**:
1. Aligns with documented intent (line 185: entities provide satisfaction status)
2. Improves code quality and maintainability
3. Enables better user experience (real-time state updates)
4. Low risk, high benefit
5. Foundation for future enhancements

**Implementation Strategy**:
- Start with Phase 1 (foundation) while maintaining backward compatibility
- Add Phase 2 (sensors) as new features
- Complete Phase 3 (cleanup) after thorough testing
- Ensure comprehensive documentation and tests

---

## Questions for Clarification

Before proceeding with implementation, please confirm:

1. **Rising/Falling Sensors**: Should these be:
   - Binary sensors (on/off)? ✓ Recommended
   - OR discrete sensors with values (rising/falling/stable)?
   - OR just entity attributes (not separate sensors)?

2. **Temperature Direction Threshold**: What threshold for detecting rising/falling?
   - Suggested: 0.05°C change over 30-60 seconds
   - Configurable per zone? Or global config?

3. **Debouncing**: Should satisfaction state changes be debounced?
   - Suggested: 5-10 seconds to prevent rapid state flapping
   - Configurable?

4. **Backward Compatibility**: During development, should both old and new logic coexist?
   - Suggested: Yes, with feature flag to toggle between implementations

5. **Redis Write Frequency**: Should zone entities write to Redis on every temperature update?
   - Suggested: Yes, but with debouncing (max 1 write per 5 seconds)

---

## Next Steps

**If Approved**:
1. Create detailed technical specifications for Phase 1
2. Set up development environment
3. Implement Climate Zone Entity with satisfaction calculation
4. Add comprehensive unit tests
5. Document changes and update diagrams

**Timeline Estimate**:
- Phase 1: 2-3 days (foundation)
- Phase 2: 1 day (sensors)
- Phase 3: 1 day (cleanup)
- Phase 4: 1 day (documentation)
- Phase 5: 2 days (testing)
- **Total**: ~7-8 days development time

---

## Conclusion

This refactoring proposal aligns perfectly with the documented architecture where zone climate entities should provide satisfaction status. It simplifies the Update Valves job, enables real-time state updates, and provides better integration with Home Assistant's entity model.

The proposed changes are low-risk, high-benefit, and lay a solid foundation for future enhancements.

**Recommendation**: Proceed with implementation after addressing the clarification questions above.
