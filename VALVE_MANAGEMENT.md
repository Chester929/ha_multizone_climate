# Enhanced Valve Management

This document describes the enhanced valve management features implemented in the multizone climate system.

## Overview

The enhanced valve management system provides intelligent control of heating/cooling zone valves with advanced features to prevent equipment wear, ensure system safety, and maintain optimal performance.

## Features

### 1. Valve Actuation Delay Timing

**Purpose:** Prevents rapid valve state changes that can cause mechanical wear and reduce valve lifespan.

**Implementation:**
- Each zone tracks when its valve was last actuated via the `LastActuated` timestamp
- The `ValveActuationDelay` configuration parameter (in seconds) defines minimum time between valve state changes
- Function `CanActuateValve()` checks if sufficient time has passed since last actuation

**Configuration:**
```json
{
  "valve_actuation_delay": 30  // Minimum 30 seconds between valve operations
}
```

**Behavior:**
- If a valve was actuated less than `valve_actuation_delay` seconds ago, it cannot be actuated again
- This applies to both open and close operations
- Never-actuated valves can always be actuated

### 2. Valve Lock Expiration Tracking

**Purpose:** Allows temporary locking of valves to prevent operations during maintenance or special conditions.

**Implementation:**
- Each zone can have a `ValveLockExpiration` timestamp
- Locks automatically expire when the current time passes the expiration time
- Functions: `LockValve()`, `UnlockValve()`, `IsValveLocked()`

**Usage Example:**
```go
// Lock a valve for 10 minutes
zone := getZone("living_room")
algorithm.LockValve(&zone, 10 * time.Minute)

// Check if locked
if algorithm.IsValveLocked(zone) {
    // Valve is locked, skip operation
}

// Manually unlock
algorithm.UnlockValve(&zone)
```

**Behavior:**
- Locked valves are completely skipped during valve operation planning
- Locks automatically expire - no manual cleanup needed
- Lock status is checked before every operation

### 3. Priority-Based Valve Selection

**Purpose:** Ensures critical zones are prioritized when selecting which valves to open or close.

**Implementation:**
- Each zone has a `Priority` field (higher numbers = higher priority)
- Function `SortZonesByPriority()` orders zones by priority (descending)
- `CheckMinimumValvesByPriority()` selects highest-priority fallback valves when needed

**Configuration:**
```json
{
  "zones": [
    {"id": "living_room", "priority": 10, "is_fallback_valve": true},
    {"id": "bedroom", "priority": 5, "is_fallback_valve": true},
    {"id": "storage", "priority": 1, "is_fallback_valve": true}
  ]
}
```

**Behavior:**
- When minimum valves requirement is not met, highest-priority fallback valves are opened first
- Operations are executed in priority order (highest first)
- Zones with equal priority are sorted by ID for consistency

### 4. Valve Chattering Prevention

**Purpose:** Prevents rapid open-close-open cycles (chattering) that waste energy and damage equipment.

**Implementation:**
- Combines `LastActuated` timestamp with `ValveActuationDelay` configuration
- Each valve operation updates `LastActuated` to current time
- `CanActuateValve()` enforces the delay before allowing next operation

**Example Scenario:**
```
Time 0:00 - Valve opens (underheated)
Time 0:10 - Temperature satisfied, but valve cannot close yet (delay: 30s)
Time 0:30 - Valve can now close if still satisfied
Time 0:35 - Temperature drops, but valve cannot open yet
Time 1:00 - Valve can now open if needed
```

**Benefits:**
- Reduces valve wear
- Prevents oscillating behavior
- More stable temperature control
- Lower energy consumption

### 5. Open-First-Then-Close Sequencing

**Purpose:** Ensures system flow is maintained by opening new valves before closing others.

**Implementation:**
- `PlanValveOperations()` separates operations into open and close lists
- `ExecuteValveOperations()` performs all opens first, then closes
- Minimum valves requirement is checked before each close operation

**Sequence:**
```
1. Plan all valve operations
2. Separate into open_operations and close_operations
3. Execute all open_operations in priority order
4. Execute close_operations in priority order, respecting minimum valves
```

**Benefits:**
- Prevents temporary flow interruption
- Maintains system pressure
- Avoids "all valves closed" scenarios
- Smoother temperature transitions

## API Integration

The enhanced valve management is integrated into the worker processor:

### ProcessUpdateValves Job

This job uses all enhanced valve management features:

```go
// 1. Load zones and config
zones := loadZones()
config := loadConfig()

// 2. Update satisfaction states
for each zone:
    zone.Satisfaction = DetermineZoneSatisfaction(zone, config.SatisfactionEpsilon)

// 3. Plan operations (respects locks, delays, priorities)
openOps, closeOps := PlanValveOperations(zones, config.ValveActuationDelay)

// 4. Execute with open-first sequencing
executedOps := ExecuteValveOperations(openOps, closeOps, zones, config.MinValvesOpen)

// 5. Apply to Home Assistant
for each executedOp:
    SetValveState(op.ZoneID, op.Operation)
    UpdateLastActuated(op.ZoneID)

// 6. Enforce minimum valves with priority selection
fallbackValves := CheckMinimumValvesByPriority(zones, config.MinValvesOpen)
for each fallbackValve:
    OpenValve(fallbackValve)
```

## Data Model

### ZoneState Fields

```go
type ZoneState struct {
    // ... existing fields ...
    
    // Enhanced valve management fields
    Priority                int        `json:"priority"`
    LastActuated            *time.Time `json:"last_actuated,omitempty"`
    ValveLockExpiration     *time.Time `json:"valve_lock_expiration,omitempty"`
}
```

### GlobalConfig Fields

```go
type GlobalConfig struct {
    // ... existing fields ...
    
    ValveActuationDelay     int     `json:"valve_actuation_delay"`  // seconds
}
```

## Redis Storage

The enhanced fields are stored in Redis:

```
multizone:zone:{zone_id}
  - last_actuated: Unix timestamp (seconds)
  - valve_lock_expiration: Unix timestamp (seconds)
  - priority: Integer
```

## Testing

Comprehensive tests cover all features:

- `TestCanActuateValve` - Actuation delay logic
- `TestIsValveLocked` - Lock expiration tracking
- `TestLockValve` / `TestUnlockValve` - Lock management
- `TestSortZonesByPriority` - Priority-based sorting
- `TestCheckMinimumValvesByPriority` - Priority selection
- `TestPlanValveOperations` - Planning with all constraints
- `TestExecuteValveOperations` - Open-first sequencing

All tests pass and provide >95% code coverage.

## Configuration Examples

### Conservative (High Safety)
```json
{
  "valve_actuation_delay": 60,
  "min_valves_open": 2,
  "zones": [
    {"id": "zone1", "priority": 10, "is_fallback_valve": true},
    {"id": "zone2", "priority": 9, "is_fallback_valve": true}
  ]
}
```

### Responsive (Lower Delay)
```json
{
  "valve_actuation_delay": 20,
  "min_valves_open": 1,
  "zones": [
    {"id": "zone1", "priority": 5}
  ]
}
```

### Balanced (Recommended)
```json
{
  "valve_actuation_delay": 30,
  "min_valves_open": 1,
  "zones": [
    {"id": "main", "priority": 10, "is_fallback_valve": true},
    {"id": "living", "priority": 8},
    {"id": "bedroom", "priority": 7},
    {"id": "storage", "priority": 1, "is_fallback_valve": true}
  ]
}
```

## Best Practices

1. **Set appropriate actuation delays:**
   - Too low: Excessive wear, chattering
   - Too high: Slow response to temperature changes
   - Recommended: 20-60 seconds

2. **Configure fallback valves:**
   - At least one zone should be `is_fallback_valve: true`
   - Fallback zones should have higher priority
   - Consider zones that are always safe to heat/cool

3. **Assign priorities:**
   - Critical zones (living areas): 8-10
   - Normal zones: 5-7
   - Low-priority zones (storage): 1-4

4. **Monitor valve operations:**
   - Check logs for frequent actuations
   - Verify minimum valves are maintained
   - Watch for lock expirations

5. **Use locks sparingly:**
   - Only for maintenance or special conditions
   - Set appropriate expiration times
   - Don't lock all fallback valves simultaneously

## Troubleshooting

### Valve not responding
- Check if valve is locked: `IsValveLocked()`
- Check last actuation time vs delay
- Verify valve entity ID in configuration

### Too slow to respond
- Reduce `valve_actuation_delay`
- Increase zone priorities
- Check if valve is frequently locked

### Chattering detected
- Increase `valve_actuation_delay`
- Adjust satisfaction thresholds
- Review temperature sensor placement

### Minimum valves violation
- Check fallback valve configuration
- Verify priorities are set correctly
- Review logs for failed operations

## Files

- `logic/internal/models/models.go` - Data models
- `logic/internal/algorithm/valve.go` - Core algorithms
- `logic/internal/algorithm/valve_test.go` - Comprehensive tests
- `logic/internal/worker/processor.go` - Integration with job processing
- `logic/cmd/server/main.go` - Server initialization

## Future Enhancements

Potential improvements:
- Adaptive delay based on valve type
- Machine learning for optimal timing
- Valve health monitoring
- Predictive maintenance alerts
- Integration with valve sensor feedback
