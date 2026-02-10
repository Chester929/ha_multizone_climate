# Quick Reference - Fully Autonomous Zones with Hybrid Valve Control

## At a Glance

**What**: Multi-zone HVAC climate control for Home Assistant  
**Architecture**: Fully Autonomous Zones (event-driven Python)  
**Valve Logic**: Hybrid two-tier (temperature safety + deficit magnitude)  
**Backend**: Redis only (no Go service)  
**Status**: IMPLEMENTATION READY ✅

---

## Core Concept in 30 Seconds

Each zone is a self-governing climate entity that:
1. **Listens** to its temperature sensor
2. **Calculates** satisfaction state (underheated/satisfied/overheated)
3. **Decides** valve action using hybrid logic:
   - Tier 1: Would this overheat me? (temperature check)
   - Tier 2: Is there a large deficit elsewhere? (prioritization)
4. **Executes** valve open/close directly
5. **Writes** state to Redis for coordination

---

## Key Components

| Component | Purpose | Type |
|-----------|---------|------|
| `AutonomousZoneClimate` | Self-governing zone entity | ClimateEntity |
| `SatisfactionCalculator` | State machine with hysteresis | Pure logic |
| `HybridValveController` | Two-tier valve decision | Pure logic |
| `MainClimateCoordinator` | Calculate main temp (periodic) | DataUpdateCoordinator |
| `SafetyCoordinator` | Ensure min valves open | DataUpdateCoordinator |
| `ValveManager` | Execute valve actions | Service caller |
| `RedisClient` | State storage | Redis interface |

---

## Decision Flow

```
Temperature Change Event
  ↓
Calculate Satisfaction (underheated/satisfied/overheated)
  ↓
Determine Valve Action:
  • Underheated? → OPEN
  • Overheated? → CLOSE
  • Satisfied? → Hybrid Logic:
      ├─ No underheated zones? → OPEN
      ├─ Tier 1: main_target > (zone_target + offset)? → CLOSE
      ├─ Tier 2: max_deficit > threshold? → CLOSE
      └─ Both pass → OPEN
  ↓
Execute Valve Action (with safety checks)
  ↓
Write State to Redis
```

---

## Configuration Example

```yaml
# Main climate
main_climate_entity_id: climate.main_thermostat

# Zone configuration
zones:
  bedroom:
    name: Bedroom
    temp_sensor: sensor.bedroom_temperature
    valve_switch: switch.bedroom_valve
    target_temperature: 21.0
    upper_offset: 0.3              # Overheat threshold
    satisfaction_epsilon: 0.1       # Hysteresis buffer
    deficit_threshold: 1.0          # Tier 2 threshold
    valve_delay: 120                # Seconds between actions
    is_fallback: false

# Global settings
min_valves_open: 1
main_coordinator_interval: 30      # Seconds
safety_check_interval: 60          # Seconds
```

---

## Main Target Calculation

**Heating Mode**:

```python
if underheated_zones:
    main_target = main_current + max_zone_deficit
elif satisfied_zones:
    main_target = average(zone_targets)
elif overheated_zones:
    main_target = min(zone_targets)
```

**Example**:
- Kitchen: 22°C → 24°C (deficit 2°C)
- Bedroom: 21°C satisfied
- Main current: 23°C
- **Result**: main_target = 23 + 2 = 25°C

---

## Hybrid Valve Logic

**Example Scenario**:
```
Kitchen underheated (2°C deficit) → Main boosted to 25°C
Bedroom satisfied at 21°C (upper_offset 0.3, deficit_threshold 1.0)

Bedroom valve decision:
  Satisfaction: "satisfied"
  Underheated zones: yes (Kitchen)
  
  Tier 1 check:
    overheat_threshold = 21 + 0.3 = 21.3°C
    main_target = 25°C
    25 > 21.3? YES → CLOSE ✅
    (Tier 2 not evaluated)
  
  Result: Bedroom valve CLOSED (prevents overheating)
```

---

## File Structure

```
custom_components/multizone_climate/
├── __init__.py                    # Integration setup
├── manifest.json                  # Metadata
├── climate.py                     # AutonomousZoneClimate
├── coordinator.py                 # Main & Safety coordinators
├── config_flow.py                 # User configuration
├── const.py                       # Constants
├── services.yaml                  # Service definitions
└── core/
    ├── satisfaction.py            # SatisfactionCalculator
    ├── hybrid_valve.py            # HybridValveController
    ├── valve_manager.py           # ValveManager
    └── redis_client.py            # RedisClient

addon/
├── config.yaml                    # Addon config
├── Dockerfile                     # Redis container
└── rootfs/                        # Container filesystem
```

---

## Redis Data

### Zone State
```json
{
  "zone_id": "bedroom",
  "current_temperature": 21.0,
  "target_temperature": 21.0,
  "satisfaction": "satisfied",
  "valve_state": "open",
  "is_fallback": false,
  "enabled": true,
  "updated_at": 1707565200.0
}
```

### Main Climate State
```json
{
  "target_temperature": 23.5,
  "current_temperature": 23.0,
  "updated_at": 1707565200.0
}
```

---

## Implementation Phases

1. **Week 1**: Core logic (SatisfactionCalculator, HybridValveController)
2. **Week 2**: Redis client, Valve manager, Zone entity
3. **Week 3**: Coordinators, Integration wiring
4. **Week 4**: Config flow, Addon
5. **Week 5**: Testing, Documentation, Release

---

## Testing Checklist

**Unit Tests**:
- [ ] SatisfactionCalculator (all states, hysteresis)
- [ ] HybridValveController (all decision paths)
- [ ] Main target calculation
- [ ] Valve manager

**Integration Tests**:
- [ ] Zone entity event handling
- [ ] Hybrid logic prevents overheating
- [ ] Safety coordinator enforces min valves
- [ ] Redis state persistence

**E2E Tests**:
- [ ] Morning warmup scenario
- [ ] Single zone heating
- [ ] All satisfied equilibrium
- [ ] 24-hour stability

---

## Key Metrics

**Performance Targets**:
- Event processing: < 100ms
- Valve decision: < 10ms
- Redis operations: < 50ms
- Memory usage: < 50MB

**Operational Targets**:
- Valve actions: < 10 per hour per zone
- State transitions: Smooth, no oscillation
- Uptime: 99.9%

---

## Common Patterns

### Event Handler Pattern
```python
async def async_added_to_hass(self):
    """Register event listener."""
    self.async_on_remove(
        async_track_state_change_event(
            self.hass,
            [self.temp_sensor_id],
            self._handle_temperature_change,
        )
    )

async def _handle_temperature_change(self, event):
    """Handle temp change - autonomous logic."""
    if (new_state := event.data.get("new_state")) is None:
        return
    # ... process event
    await self._write_state_to_redis()
```

### Safety Check Pattern
```python
async def _execute_valve_action(self, action: str):
    """Execute with safety checks."""
    if action == "close":
        if not await self._check_can_close_valve():
            _LOGGER.warning("Cannot close - safety violation")
            return
    
    await self.valve_manager.execute_action(action)
```

### Redis Pattern
```python
async def _write_state_to_redis(self):
    """Write state with error handling."""
    try:
        state = {
            "zone_id": self.zone_id,
            "current_temperature": self._current_temperature,
            # ... other fields
        }
        await self.redis_client.set_zone_state(self.zone_id, state)
    except RedisError as e:
        _LOGGER.error(f"Redis write failed: {e}")
        # Continue operation with cached state
```

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Zone not responding | Event listener not registered | Check `async_added_to_hass()` logs |
| Valve not actuating | Actuation delay | Check time since last action |
| All valves closed | Safety coordinator issue | Check fallback zone config |
| Oscillating | Epsilon too small | Increase satisfaction_epsilon |
| Overheating | Hybrid logic issue | Check tier 1/2 logs |

---

## Best Practices

**DO**:
- ✅ Use `hass.async_create_task()` for async operations
- ✅ Validate event data before processing
- ✅ Write state to Redis on every change
- ✅ Handle all exceptions gracefully
- ✅ Log decision rationale clearly

**DON'T**:
- ❌ Block in event handlers
- ❌ Assume entities exist
- ❌ Close last valve without fallback
- ❌ Allow rapid valve cycling
- ❌ Store critical state only in memory

---

## Resources

**Main Documents**:
- `COMPLETE_SOLUTION_DESIGN.md` - Full specification (41KB)
- `IMPLEMENTATION_GUIDE.md` - Step-by-step instructions (17KB)
- `OPTION3_HYBRID_VALVE_CONTROL.md` - Hybrid logic details (30KB)
- `OPTION3_BUSINESS_LOGIC.md` - All scenarios (15KB)
- `OPTION3_ARCHITECTURE.md` - System architecture (34KB)

**External References**:
- Home Assistant Developer Docs
- Redis Python Client Docs
- HA Custom Component Best Practices

---

## Quick Start for Implementers

1. **Read**: `COMPLETE_SOLUTION_DESIGN.md` (full spec)
2. **Follow**: `IMPLEMENTATION_GUIDE.md` (step-by-step)
3. **Start**: Phase 1 - Core logic components
4. **Test**: Write unit tests as you implement
5. **Iterate**: Build incrementally, test often

---

## Decision Summary

**Architecture**: Fully Autonomous Zones ✅
- Event-driven Python zones
- No Go backend
- Redis for state only
- Direct valve control

**Valve Logic**: Hybrid Control ✅
- Tier 1: Temperature safety
- Tier 2: Deficit prioritization
- Configurable thresholds
- Smart optimization

**Status**: IMPLEMENTATION READY ✅
- All design decisions made
- Full specifications documented
- Test strategy defined
- No blocking questions

---

**This is a complete, greenfield implementation. Start fresh, build incrementally, test thoroughly.**
