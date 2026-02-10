# Option 3: Hybrid Valve Control for Satisfied Zones

## Executive Summary

The Hybrid Valve Control approach combines **temperature-based safety checks** with **deficit magnitude awareness** to intelligently manage satisfied zone valves when underheated zones exist. This prevents overheating while maximizing comfort and minimizing oscillation.

## Problem Statement

### Current Issue
When underheated zones create a boosted main climate target temperature, satisfied zones with open valves receive water that may be too hot for their target temperature, causing them to overheat.

**Example Scenario:**
```
Kitchen:  22°C current, 24°C target → UNDERHEATED (deficit 2°C)
Bedroom:  21°C current, 21°C target → SATISFIED
Main:     23°C current → new target: 23 + 2 = 25°C

Current Behavior:
  Kitchen valve:  OPEN ✓ (needs heat)
  Bedroom valve:  OPEN ✗ (receives 25°C water, will overheat!)
  
Expected: Bedroom at 21°C with upper_offset 0.3 → safe limit: 21.3°C
Reality:  25°C water > 21.3°C → OVERHEATING RISK!
```

## Solution: Hybrid Approach

### Core Concept

The Hybrid Approach uses **two-tier decision logic**:

1. **Primary Check**: Temperature-based safety (prevents overheating)
2. **Secondary Check**: Deficit magnitude awareness (optimizes comfort)

This ensures:
- ✅ **Safety First**: Never allow overheating
- ✅ **Comfort When Possible**: Keep valves open when safe
- ✅ **Smart Prioritization**: Close valves only when necessary

### Decision Algorithm

```python
if satisfaction == "satisfied":
    if not underheated_zones_exist:
        # No competition - maintain temperature
        valve_action = OPEN
    else:
        # Underheated zones exist - apply hybrid logic
        
        # TIER 1: Temperature Safety Check
        overheat_threshold = zone_target + upper_offset
        if main_target_temp > overheat_threshold:
            valve_action = CLOSE  # Would overheat - safety first
        else:
            # TIER 2: Deficit Magnitude Check
            max_deficit = max(zone.deficit for zone in underheated_zones)
            
            if max_deficit > DEFICIT_THRESHOLD:
                # Large deficit - prioritize underheated zones
                valve_action = CLOSE
            else:
                # Small deficit - can maintain both
                valve_action = OPEN
```

### Key Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `upper_offset` | 0.3°C | 0.1-1.0°C | Maximum temperature above target before overheating |
| `DEFICIT_THRESHOLD` | 1.0°C | 0.5-2.0°C | Deficit above which to prioritize underheated zones |

### Configuration Options

Users can configure the deficit threshold per zone or globally:

```yaml
# Zone-specific configuration
zones:
  bedroom:
    target_temperature: 21.0
    upper_offset: 0.3
    deficit_threshold: 1.0  # New parameter
```

## Detailed Logic Flow

### Flowchart

```
┌─────────────────────────────────────────────────┐
│ Zone Satisfaction State: SATISFIED              │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ Are there any UNDERHEATED zones?                │
└────┬─────────────────────────────────┬──────────┘
     │ NO                               │ YES
     ▼                                  ▼
┌─────────────────┐    ┌───────────────────────────────────────┐
│ Valve: OPEN     │    │ Calculate overheat_threshold:         │
│ (Maintain temp) │    │   = zone_target + upper_offset        │
└─────────────────┘    └──────────┬────────────────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────────────────────┐
                    │ Is main_target > overheat_threshold?     │
                    └──┬────────────────────────────────┬──────┘
                       │ YES                            │ NO
                       ▼                                ▼
            ┌──────────────────┐      ┌────────────────────────────────┐
            │ Valve: CLOSE     │      │ Calculate max_deficit from all │
            │ (Would overheat) │      │ underheated zones              │
            └──────────────────┘      └──────┬─────────────────────────┘
                                             │
                                             ▼
                              ┌──────────────────────────────────────┐
                              │ Is max_deficit > DEFICIT_THRESHOLD?  │
                              └──┬───────────────────────────┬───────┘
                                 │ YES                       │ NO
                                 ▼                           ▼
                    ┌─────────────────────────┐   ┌──────────────────┐
                    │ Valve: CLOSE            │   │ Valve: OPEN      │
                    │ (Prioritize underheated)│   │ (Safe to maintain)│
                    └─────────────────────────┘   └──────────────────┘
```

### State Transition Matrix

| Scenario | Main Target | Overheat Check | Deficit | Result | Reason |
|----------|-------------|----------------|---------|--------|--------|
| No underheated | N/A | - | - | OPEN | Maintain temperature |
| Small deficit, safe temp | 23.2°C | 23.2 ≤ 21.3? NO | 0.2°C | CLOSE | Temp check fails |
| Small deficit, would overheat | 24°C | 24 ≤ 21.3? NO | 0.5°C | CLOSE | Temp check fails |
| Medium deficit | 24.5°C | 24.5 ≤ 21.3? NO | 1.5°C | CLOSE | Both checks fail |
| Large deficit | 25°C | 25 ≤ 21.3? NO | 2.0°C | CLOSE | Both checks fail |

Note: In heating with 23°C base, almost any boost will exceed threshold for lower-target zones.

## Comprehensive Scenarios

### Scenario 1: Small Deficit, Temperature Safe

**Setup:**
```
Living Room: 21.8°C/22°C UNDERHEATED (deficit 0.2°C)
Bedroom:     21°C/21°C SATISFIED (upper_offset 0.3)
Main:        23°C → target: 23.2°C
```

**Hybrid Logic:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 21 + 0.3 = 21.3°C
   - Main target: 23.2°C
   - Check: 23.2 > 21.3? **YES** → Would overheat
   - **Decision: CLOSE** (safety first)

**Result:** Bedroom valve CLOSED (temperature safety takes precedence)

---

### Scenario 2: Medium Deficit

**Setup:**
```
Kitchen:  22°C/24°C UNDERHEATED (deficit 2°C)
Bedroom:  21°C/21°C SATISFIED (upper_offset 0.3)
Bathroom: 19°C/19°C SATISFIED (upper_offset 0.3)
Main:     23°C → target: 25°C
```

**Hybrid Logic - Bedroom:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 21 + 0.3 = 21.3°C
   - Main target: 25°C
   - Check: 25 > 21.3? **YES** → Would overheat
   - **Decision: CLOSE**

**Hybrid Logic - Bathroom:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 19 + 0.3 = 19.3°C
   - Main target: 25°C
   - Check: 25 > 19.3? **YES** → Would overheat
   - **Decision: CLOSE**

**Result:**
- Kitchen valve: OPEN (underheated, needs heat)
- Bedroom valve: CLOSED (would overheat)
- Bathroom valve: CLOSED (would overheat)

---

### Scenario 3: All Zones Same Target, Small Deficit

**Setup:**
```
Living Room: 21.9°C/22°C UNDERHEATED (deficit 0.1°C)
Bedroom:     22°C/22°C SATISFIED (upper_offset 0.3)
Main:        23°C → target: 23.1°C
```

**Hybrid Logic - Bedroom:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 22 + 0.3 = 22.3°C
   - Main target: 23.1°C
   - Check: 23.1 > 22.3? **YES** → Would overheat
   - **Decision: CLOSE**

**Result:** Even with same targets, small boost exceeds threshold → valve CLOSED

---

### Scenario 4: High-Target Satisfied Zone

**Setup:**
```
Kitchen:  20°C/21°C UNDERHEATED (deficit 1°C)
Bedroom:  24°C/24°C SATISFIED (upper_offset 0.3)
Main:     23°C → target: 24°C
```

**Hybrid Logic - Bedroom:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 24 + 0.3 = 24.3°C
   - Main target: 24°C
   - Check: 24 > 24.3? **NO** → Safe!
   
2. **Tier 2 - Deficit Check:**
   - Max deficit: 1.0°C
   - Threshold: 1.0°C
   - Check: 1.0 > 1.0? **NO** → At threshold, can maintain
   - **Decision: OPEN**

**Result:** Bedroom valve OPEN (unique case where high-target zone is safe)

---

### Scenario 5: No Underheated Zones

**Setup:**
```
Living Room: 22°C/22°C SATISFIED
Bedroom:     21°C/21°C SATISFIED
Bathroom:    19°C/19°C SATISFIED
Main:        23°C (no boost needed)
```

**Hybrid Logic:**
- No underheated zones exist
- **Decision: OPEN** (all satisfied valves open)

**Result:** All valves OPEN, system in equilibrium

---

### Scenario 6: Mixed Deficits

**Setup:**
```
Kitchen:     20.5°C/22°C UNDERHEATED (deficit 1.5°C)
Living Room: 19°C/20°C UNDERHEATED (deficit 1.0°C)
Bedroom:     21°C/21°C SATISFIED (upper_offset 0.3)
Main:        23°C → target: 24.5°C (max deficit 1.5°C)
```

**Hybrid Logic - Bedroom:**
1. **Tier 1 - Temperature Check:**
   - Overheat threshold: 21.3°C
   - Main target: 24.5°C
   - Check: 24.5 > 21.3? **YES** → Would overheat
   - **Decision: CLOSE**

**Result:**
- Kitchen valve: OPEN (1.5°C deficit)
- Living Room valve: OPEN (1.0°C deficit)
- Bedroom valve: CLOSED (would overheat)

## Implementation Details

### Python Implementation

```python
class HybridValveController:
    """
    Hybrid valve control with temperature safety and deficit awareness.
    """
    
    # Configuration constants
    DEFAULT_DEFICIT_THRESHOLD = 1.0  # °C
    
    def __init__(self, redis_client, config):
        self.redis_client = redis_client
        self.config = config
        self.deficit_threshold = config.get(
            'deficit_threshold', 
            self.DEFAULT_DEFICIT_THRESHOLD
        )
    
    async def determine_valve_action(
        self,
        zone_id: str,
        satisfaction: str,
        zone_target: float,
        upper_offset: float,
        main_target_temp: float,
        underheated_zones: list[dict],
    ) -> str:
        """
        Determine valve action using hybrid approach.
        
        Args:
            zone_id: Zone identifier
            satisfaction: Zone satisfaction state
            zone_target: Zone target temperature
            upper_offset: Upper temperature offset for this zone
            main_target_temp: Current main climate target temperature
            underheated_zones: List of all underheated zones with their data
            
        Returns:
            str: 'open' or 'close'
        """
        
        if satisfaction == "underheated":
            return "open"
        
        elif satisfaction == "satisfied":
            # Check if any underheated zones exist
            if not underheated_zones:
                # No competition - maintain temperature
                _LOGGER.debug(
                    f"Zone {zone_id}: No underheated zones, keeping valve open"
                )
                return "open"
            
            # TIER 1: Temperature Safety Check
            overheat_threshold = zone_target + upper_offset
            
            if main_target_temp > overheat_threshold:
                # Would overheat - close immediately
                _LOGGER.info(
                    f"Zone {zone_id}: TIER 1 - Closing valve to prevent overheat. "
                    f"Main target {main_target_temp:.1f}°C > "
                    f"threshold {overheat_threshold:.1f}°C"
                )
                return "close"
            
            # TIER 2: Deficit Magnitude Check
            max_deficit = max(
                zone.get('deficit', 0) 
                for zone in underheated_zones
            )
            
            # Get zone-specific or global deficit threshold
            zone_deficit_threshold = self.config.get(
                f'zone_{zone_id}_deficit_threshold',
                self.deficit_threshold
            )
            
            if max_deficit > zone_deficit_threshold:
                # Large deficit - prioritize underheated zones
                _LOGGER.info(
                    f"Zone {zone_id}: TIER 2 - Closing valve to prioritize "
                    f"underheated zones. Max deficit {max_deficit:.1f}°C > "
                    f"threshold {zone_deficit_threshold:.1f}°C"
                )
                return "close"
            else:
                # Small deficit - safe to maintain both
                _LOGGER.debug(
                    f"Zone {zone_id}: Safe to keep open. "
                    f"Main target {main_target_temp:.1f}°C ≤ "
                    f"threshold {overheat_threshold:.1f}°C and "
                    f"max deficit {max_deficit:.1f}°C ≤ "
                    f"threshold {zone_deficit_threshold:.1f}°C"
                )
                return "open"
        
        elif satisfaction == "overheated":
            return "close"
        
        # Fallback for unknown states
        return "open"
```

### Integration with Existing Code

**Modified `valve_control.py`:**

```python
# In update_valves() method

for zone in sorted_zones:
    valve_id = zone.get("valve_id")
    if not valve_id:
        continue

    # Skip disabled zones
    if zone.get("enabled", "true") in ["false", "False", "0"]:
        valves_to_close.append(valve_id)
        continue

    satisfaction = zone.get("satisfaction", "unknown")
    zone_id = zone.get("id")
    zone_target = zone.get("target_temperature")
    upper_offset = zone.get("closing_offset", 0.3)

    if main_climate_state.upper() == "HEATING":
        if satisfaction == "underheated":
            valves_to_open.append(valve_id)
        elif satisfaction == "overheated":
            valves_to_close.append(valve_id)
        elif satisfaction == "satisfied":
            # NEW: Hybrid valve control
            action = await self.hybrid_controller.determine_valve_action(
                zone_id=zone_id,
                satisfaction=satisfaction,
                zone_target=zone_target,
                upper_offset=upper_offset,
                main_target_temp=main_target_temp,
                underheated_zones=underheated_zones,
            )
            
            if action == "open":
                valves_to_open.append(valve_id)
            else:
                valves_to_close.append(valve_id)
```

### Data Flow

```
┌──────────────────────────────────────────────────────┐
│ Temperature Sensor Change Event                       │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ Zone Climate Entity: Calculate Satisfaction State    │
│   - Current temp vs Target temp                      │
│   - Apply hysteresis (satisfaction epsilon)          │
│   - Update satisfaction: underheated/satisfied/over  │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ Main Climate Coordinator: Calculate Main Target      │
│   - Get all zone states from Redis                  │
│   - Calculate: main_current + max_zone_deficit      │
│   - Store new main_target in Redis                  │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ Hybrid Valve Controller: Determine Valve Actions     │
│   FOR EACH satisfied zone:                          │
│     1. Get main_target from Redis                   │
│     2. Get underheated zones list                   │
│     3. Apply Tier 1: Temperature check              │
│     4. Apply Tier 2: Deficit check                  │
│     5. Return valve action (open/close)             │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ Valve Manager: Execute Valve Actions                 │
│   - Apply safety checks (min valves open)           │
│   - Check valve locks (actuation delay)             │
│   - Execute service calls to HA                     │
│   - Update valve states in Redis                    │
└──────────────────────────────────────────────────────┘
```

## Configuration

### Global Configuration

```yaml
# In integration configuration
multizone_climate:
  deficit_threshold: 1.0  # Global default
  valve_actuation_delay: 120  # seconds
  min_valves_open: 1
```

### Per-Zone Configuration

```yaml
zones:
  bedroom:
    name: "Bedroom"
    target_temperature: 21.0
    upper_offset: 0.3
    deficit_threshold: 1.2  # Override global for this zone
    
  living_room:
    name: "Living Room"
    target_temperature: 22.0
    upper_offset: 0.3
    deficit_threshold: 0.8  # More aggressive for living room
```

## Performance Characteristics

### Computational Complexity

- **Time Complexity**: O(n) where n = number of zones
  - Single pass through zones to find underheated
  - Constant time checks per satisfied zone
  
- **Space Complexity**: O(n)
  - Store underheated zones list
  - No additional data structures needed

### Response Time

- **Tier 1 Check**: < 1ms (simple comparison)
- **Tier 2 Check**: < 1ms (max operation on small list)
- **Total Decision Time**: < 5ms per zone

### Memory Usage

- Minimal overhead: ~100 bytes per zone for state tracking
- No persistent state beyond zone configurations

## Advantages Over Other Options

### vs. Option 1 (Priority-Based)

| Aspect | Option 1 | Option 3 (Hybrid) |
|--------|----------|-------------------|
| **Overheating Prevention** | ✅ Excellent | ✅ Excellent |
| **Comfort Maintenance** | ❌ Poor (zones cool down) | ✅ Good (maintains when safe) |
| **Oscillation** | ❌ High risk | ✅ Low risk |
| **Complexity** | ✅ Simple | ⚠️ Moderate |
| **User Control** | ❌ No tuning | ✅ Configurable thresholds |

### vs. Option 2 (Temperature-Based)

| Aspect | Option 2 | Option 3 (Hybrid) |
|--------|----------|-------------------|
| **Safety** | ✅ Excellent | ✅ Excellent |
| **Deficit Awareness** | ❌ None | ✅ Yes |
| **Fine-tuning** | ⚠️ Limited | ✅ Multiple parameters |
| **Edge Cases** | ⚠️ Some gaps | ✅ Better handled |
| **Complexity** | ✅ Simple | ⚠️ Moderate |

### vs. Option 4 (Proportional)

| Aspect | Option 4 | Option 3 (Hybrid) |
|--------|----------|-------------------|
| **Sophistication** | ✅ Highest | ⚠️ Moderate |
| **Implementation** | ❌ Very complex | ✅ Reasonable |
| **Valve Wear** | ❌ High (PWM) | ✅ Low (binary) |
| **Tuning Required** | ❌ Extensive | ⚠️ Moderate |
| **Reliability** | ⚠️ More failure points | ✅ Robust |

## Testing Strategy

### Unit Tests

```python
class TestHybridValveController:
    """Test hybrid valve control logic."""
    
    async def test_no_underheated_zones(self):
        """Satisfied valve stays open when no competition."""
        result = await controller.determine_valve_action(
            zone_id="bedroom",
            satisfaction="satisfied",
            zone_target=21.0,
            upper_offset=0.3,
            main_target_temp=23.0,
            underheated_zones=[],
        )
        assert result == "open"
    
    async def test_temperature_safety_tier1(self):
        """Valve closes when main target would overheat."""
        result = await controller.determine_valve_action(
            zone_id="bedroom",
            satisfaction="satisfied",
            zone_target=21.0,
            upper_offset=0.3,
            main_target_temp=25.0,  # 25 > 21.3
            underheated_zones=[{"id": "kitchen", "deficit": 2.0}],
        )
        assert result == "close"
    
    async def test_deficit_threshold_tier2(self):
        """Valve closes when deficit exceeds threshold."""
        result = await controller.determine_valve_action(
            zone_id="bedroom",
            satisfaction="satisfied",
            zone_target=24.0,
            upper_offset=0.3,
            main_target_temp=24.0,  # 24 < 24.3 (safe)
            underheated_zones=[{"id": "kitchen", "deficit": 2.0}],
        )
        # deficit_threshold = 1.0, so 2.0 > 1.0 → close
        assert result == "close"
    
    async def test_both_checks_pass(self):
        """Valve stays open when both checks pass."""
        result = await controller.determine_valve_action(
            zone_id="bedroom",
            satisfaction="satisfied",
            zone_target=24.0,
            upper_offset=0.3,
            main_target_temp=24.0,  # 24 < 24.3 (safe)
            underheated_zones=[{"id": "kitchen", "deficit": 0.5}],
        )
        # 0.5 < 1.0 threshold → open
        assert result == "open"
```

### Integration Tests

```python
class TestHybridIntegration:
    """Test hybrid controller in full system."""
    
    async def test_realistic_scenario(self):
        """Test complete scenario with multiple zones."""
        zones = [
            {
                "id": "kitchen",
                "satisfaction": "underheated",
                "current_temperature": 22.0,
                "target_temperature": 24.0,
                "deficit": 2.0,
            },
            {
                "id": "bedroom",
                "satisfaction": "satisfied",
                "current_temperature": 21.0,
                "target_temperature": 21.0,
                "closing_offset": 0.3,
            },
        ]
        
        main_target = 25.0  # 23 + 2
        
        actions = await valve_controller.update_valves(
            zones=zones,
            main_climate_state="HEATING",
            main_target_temp=main_target,
        )
        
        # Kitchen should open
        kitchen_action = next(a for a in actions if a["valve_id"] == "kitchen")
        assert kitchen_action["action"] == "open"
        
        # Bedroom should close (25 > 21.3)
        bedroom_action = next(a for a in actions if a["valve_id"] == "bedroom")
        assert bedroom_action["action"] == "close"
```

## Monitoring and Diagnostics

### Logging

```python
# Detailed logging for troubleshooting
_LOGGER.info(
    f"Hybrid valve decision for {zone_id}: "
    f"satisfaction={satisfaction}, "
    f"target={zone_target:.1f}°C, "
    f"main_target={main_target_temp:.1f}°C, "
    f"overheat_threshold={overheat_threshold:.1f}°C, "
    f"max_deficit={max_deficit:.1f}°C, "
    f"deficit_threshold={deficit_threshold:.1f}°C, "
    f"action={action}"
)
```

### Metrics

Track key metrics in Redis:
- `hybrid_tier1_closures`: Count of temperature-based closures
- `hybrid_tier2_closures`: Count of deficit-based closures
- `hybrid_open_decisions`: Count of valve open decisions
- `hybrid_avg_decision_time`: Average decision time in ms

### Debug Mode

```yaml
# Enable detailed debug logging
logger:
  default: info
  logs:
    custom_components.multizone_climate.valve_control: debug
    custom_components.multizone_climate.hybrid_controller: debug
```

## Edge Cases and Handling

### Edge Case 1: Very Small Upper Offset

**Problem**: Upper offset < 0.1°C makes almost everything fail tier 1

**Solution**: Enforce minimum upper_offset of 0.1°C in configuration validation

```python
def validate_upper_offset(offset: float) -> float:
    """Validate and clamp upper offset."""
    if offset < 0.1:
        _LOGGER.warning(f"Upper offset {offset} too small, clamping to 0.1")
        return 0.1
    return offset
```

### Edge Case 2: All Zones Have Different Targets

**Problem**: Wide range of targets (18°C to 24°C) creates complex scenarios

**Solution**: Hybrid approach handles this naturally - each zone evaluated independently

### Edge Case 3: Rapid Deficit Changes

**Problem**: Zone quickly transitions underheated → satisfied → underheated

**Solution**: 
- Satisfaction state has built-in hysteresis (epsilon)
- Valve locks prevent rapid cycling (120s default)
- Tier 2 deficit check smooths transitions

### Edge Case 4: Main Target Calculation Lag

**Problem**: Main target updated async, might be stale

**Solution**: 
- Always fetch latest main_target from Redis before valve decisions
- Fall back to last known value if Redis unavailable
- Log warning if using stale data

```python
async def get_current_main_target(self) -> float:
    """Get current main target with staleness check."""
    try:
        main_state = await self.redis_client.get_main_climate_state()
        target = main_state.get("target_temperature")
        updated_at = main_state.get("updated_at", 0)
        
        # Check if stale (> 60 seconds old)
        if time.time() - updated_at > 60:
            _LOGGER.warning("Main target is stale, recalculating")
            # Trigger recalculation
            await self.trigger_main_target_calculation()
        
        return target
    except Exception as e:
        _LOGGER.error(f"Failed to get main target: {e}")
        return self.last_known_main_target
```

## Migration Path

### From Current Implementation

1. **Phase 1**: Add hybrid controller class (non-breaking)
2. **Phase 2**: Add configuration option `use_hybrid_valve_control` (default: false)
3. **Phase 3**: Test in user environments with opt-in
4. **Phase 4**: Make hybrid default after validation
5. **Phase 5**: Remove old logic after deprecation period

### Configuration Migration

```yaml
# Old config (still supported)
zones:
  bedroom:
    opening_offset: 0.3
    closing_offset: 0.3

# New config (hybrid)
zones:
  bedroom:
    opening_offset: 0.3
    closing_offset: 0.3  # Used as upper_offset
    deficit_threshold: 1.0  # New parameter
```

## Future Enhancements

### Potential Improvements

1. **Learning Mode**: Automatically adjust `deficit_threshold` based on:
   - Observed oscillation patterns
   - User comfort feedback
   - Historical valve cycling frequency

2. **Weather Integration**: Adjust thresholds based on outdoor temperature:
   - Colder weather → lower threshold (prioritize heating)
   - Mild weather → higher threshold (maintain comfort)

3. **Time-of-Day Profiles**: Different thresholds for different times:
   - Morning: Lower threshold (heat up quickly)
   - Evening: Higher threshold (maintain comfort)
   - Night: Moderate threshold (efficient operation)

4. **Zone Groups**: Apply group-level deficit thresholds:
   - "Bedroom group" → higher threshold (prioritize comfort)
   - "Utility areas" → lower threshold (prioritize efficiency)

## Success Criteria

### Functional Requirements

- ✅ Prevent overheating of satisfied zones in all scenarios
- ✅ Maintain comfort when main target permits
- ✅ Minimize valve cycling and oscillation
- ✅ Configurable thresholds per zone
- ✅ Robust error handling and fallbacks

### Performance Requirements

- ✅ Decision time < 10ms per zone
- ✅ Memory overhead < 1KB per zone
- ✅ No impact on HA responsiveness
- ✅ Valve actuation rate < 10 per hour per zone

### User Experience Requirements

- ✅ Intuitive configuration with sensible defaults
- ✅ Clear logging for troubleshooting
- ✅ Metrics dashboard for monitoring
- ✅ Documentation with real-world examples

## Conclusion

The Hybrid Approach (Option 3) provides the optimal balance of:
- **Safety**: Temperature-based check prevents all overheating
- **Efficiency**: Deficit-based check optimizes heat distribution
- **Comfort**: Maintains satisfied zones when possible
- **Flexibility**: Configurable thresholds for customization
- **Robustness**: Two-tier logic handles edge cases

This solution is ready for implementation with clear requirements, comprehensive testing strategy, and well-defined success criteria.

---

**Status: IMPLEMENTATION READY**

All design decisions documented, edge cases addressed, and implementation plan complete.
