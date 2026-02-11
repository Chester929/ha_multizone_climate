# Updated Solution: Immediate Override & Zone Enable/Disable

## Executive Summary

Based on user clarification, the system should handle manual changes as follows:

1. **Main Climate Target Changes**: Immediately override back to calculated value (no waiting for coordinator)
2. **Valve Manual Closure (ON→OFF)**: Disable/turn off the entire zone (exclude from calculations)
3. **Valve Manual Opening (OFF→ON)**: Enable/turn on the zone + immediate valve recalculation

---

## Updated Requirements

### Requirement 1: Immediate Main Climate Target Override

**User Action**: Manually changes main climate target temperature

**Expected System Behavior**:
```
T=0s    User sets main climate to 28°C
T=0.1s  Event listener detects change (NOT from coordinator)
T=0.2s  Coordinator immediately calculates correct value (e.g., 23°C)
T=0.3s  Main climate target overridden back to 23°C
        
Result: User sees 28°C for < 1 second, then back to 23°C
```

**Key Points**:
- ✅ Immediate override (not delayed until next coordinator cycle)
- ✅ No manual override mode (always enforce calculated value)
- ✅ User cannot manually control main climate target
- ⚠️ Consider: Should we notify user why their change was reverted?

---

### Requirement 2: Valve State Changes Control Zone Enable/Disable

**User Action 1**: Turns valve OFF (ON → OFF)

**Expected System Behavior**:
```
T=0s    User turns switch.bedroom_valve OFF
T=0.1s  Event listener detects valve state change
T=0.2s  Zone bedroom is DISABLED
        - Zone excluded from all calculations
        - Zone shows as "disabled" in UI
        - Zone valve state: "closed"
        - Zone removed from coordinator calculations
T=0.3s  Main target recalculated (bedroom excluded)
T=0.4s  Other zones recalculate their valve states

Result: Bedroom zone is completely disabled, not participating
```

**User Action 2**: Turns valve ON (OFF → ON)

**Expected System Behavior**:
```
T=0s    User turns switch.bedroom_valve ON
T=0.1s  Event listener detects valve state change
T=0.2s  Zone bedroom is ENABLED
        - Zone included in calculations
        - Zone shows as "enabled" in UI
T=0.3s  Zone immediately recalculates satisfaction state
        - Based on current temperature vs target
        - Calculate: underheated/satisfied/overheated
T=0.4s  Zone immediately determines valve action
        - Apply hybrid valve logic
        - Determine: open/close
T=0.5s  Zone executes valve action if needed
        - May close valve immediately if would overheat
        - May keep valve open if needs heat
T=0.6s  Main target recalculated (bedroom included)

Result: Bedroom zone enabled and valve state determined immediately
```

**Key Points**:
- ✅ Valve state directly controls zone enable/disable
- ✅ Disabled zone = excluded from all calculations
- ✅ Enabled zone = immediate recalculation + valve decision
- ✅ No fighting between user and system
- ✅ Clear zone state (enabled/disabled)

---

## Solution Options

### Option A: Event-Driven Immediate Override (Recommended)

**For Main Climate Target Changes:**

**Implementation**:
1. Add event listener in `MainClimateCoordinator` for main climate `target_temperature` attribute changes
2. On event received:
   - Check if change originated from coordinator (track last update timestamp)
   - If external change detected:
     - Immediately trigger coordinator update (don't wait for periodic cycle)
     - Calculate correct target based on current zone states
     - Override main climate target back to calculated value
     - Log warning: "Main climate target manually changed, overriding back to calculated value"
     - Optional: Send notification to user

**For Valve State Changes:**

**Implementation**:
1. Add event listener in each `AutonomousZoneClimate` for its valve switch state changes
2. On valve OFF detected:
   - Set zone `enabled = false` (new attribute)
   - Update zone state in Redis: `enabled: false`
   - Log: "Zone {zone_id} disabled via manual valve closure"
   - Trigger main coordinator update immediately
   - Other zones recalculate based on new main target (excluding this zone)
3. On valve ON detected:
   - Set zone `enabled = true`
   - Update zone state in Redis: `enabled: true`
   - Immediately calculate satisfaction state (underheated/satisfied/overheated)
   - Immediately determine valve action (hybrid logic)
   - Execute valve action if needed
   - Log: "Zone {zone_id} enabled via manual valve opening, valve decision: {action}"
   - Trigger main coordinator update immediately

**Pros**:
- ✅ Immediate response (< 1 second)
- ✅ Clear zone enable/disable state
- ✅ No fighting with user
- ✅ System always enforces calculated main target
- ✅ User has control via valve switches (zone enable/disable)
- ✅ Safety maintained (disabled zones don't affect min valve requirement)

**Cons**:
- ⚠️ User cannot manually control main climate target at all
- ⚠️ Need to track coordinator vs external changes
- ⚠️ Immediate coordinator trigger may happen frequently

**Effort**: 8-10 hours

**Components to Modify**:
- `MainClimateCoordinator`: Add event listener + immediate override logic
- `AutonomousZoneClimate`: Add valve state listener + enable/disable logic
- `algorithms.py`: Respect `enabled` flag in calculations
- `RedisClient`: Add `enabled` field to zone state
- Configuration: Add `enabled` to zone config schema

---

### Option B: Service-Call Based Control

**For Main Climate Target Changes:**

**Implementation**:
- Same as Option A (event listener + immediate override)

**For Valve State Changes:**

**Implementation**:
1. Add Home Assistant services:
   - `multizone_climate.disable_zone`
   - `multizone_climate.enable_zone`
2. Add automation template for users:
   ```yaml
   automation:
     - trigger:
         platform: state
         entity_id: switch.bedroom_valve
         to: 'off'
       action:
         service: multizone_climate.disable_zone
         data:
           zone_id: bedroom
   ```
3. Implement services to set zone enabled/disabled

**Pros**:
- ✅ Explicit user intent via services
- ✅ Can be used in automations
- ✅ Clear separation of concerns

**Cons**:
- ❌ Requires users to create automations
- ❌ Not automatic (valve state doesn't directly control zone)
- ❌ More complex setup

**Effort**: 6-8 hours

**Not Recommended**: Requires manual automation setup by users.

---

### Option C: Configuration-Based Behavior

**Implementation**:
- Add per-zone config: `manual_valve_controls_zone: true/false`
- If true: valve state controls zone enable/disable (Option A)
- If false: ignore valve state changes (current behavior)

**Pros**:
- ✅ Flexible per-zone configuration
- ✅ Backward compatible

**Cons**:
- ⚠️ More configuration complexity
- ⚠️ Inconsistent behavior across zones

**Effort**: 10-12 hours

---

## Recommended Solution: Option A

**Implementation Details**:

### 1. Main Climate Target Override (Immediate)

**File**: `coordinator.py` - `MainClimateCoordinator`

**Add**:
```python
class MainClimateCoordinator(DataUpdateCoordinator):
    def __init__(self, ...):
        # ... existing init
        self._last_target_update_time = None
        
    async def async_added_to_hass(self):
        """Register event listeners."""
        await super().async_added_to_hass()
        
        # Listen for main climate target temperature changes
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.main_climate_entity_id],
                self._handle_main_climate_target_change,
            )
        )
    
    async def _handle_main_climate_target_change(self, event):
        """Handle main climate target temperature change."""
        if (new_state := event.data.get("new_state")) is None:
            return
        
        old_state = event.data.get("old_state")
        if old_state is None:
            return
        
        # Check if target temperature actually changed
        new_target = new_state.attributes.get("temperature")
        old_target = old_state.attributes.get("temperature")
        
        if new_target is None or new_target == old_target:
            return
        
        # Check if this change was made by us (coordinator)
        now = time.time()
        if (self._last_target_update_time and 
            now - self._last_target_update_time < 2.0):
            # Recent update by coordinator, ignore
            return
        
        # External change detected - override immediately
        _LOGGER.warning(
            "Main climate target manually changed to %s°C. "
            "Overriding back to calculated value.",
            new_target
        )
        
        # Trigger immediate coordinator update
        await self.async_request_refresh()
        
        # Optional: Send notification to user
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Main Climate Override",
                "message": (
                    f"Manual change to {new_target}°C was overridden. "
                    "The main climate target is automatically calculated "
                    "based on zone requirements."
                ),
            },
        )
    
    async def _async_update_data(self):
        """Update main climate target."""
        # ... existing calculation logic
        
        # Track that we're updating the target
        self._last_target_update_time = time.time()
        
        # Update main climate
        await self.hass.services.async_call(
            "climate", "set_temperature",
            {
                "entity_id": self.main_climate_entity_id,
                "temperature": calculated_target
            }
        )
        
        return calculated_target
```

**Key Points**:
- Event listener tracks main climate target changes
- Distinguishes coordinator updates from external changes (timestamp tracking)
- Immediately triggers coordinator refresh on external change
- Sends notification explaining override (optional but recommended)

---

### 2. Valve State Changes Control Zone Enable/Disable

**File**: `climate.py` - `AutonomousZoneClimate`

**Add/Modify**:
```python
class AutonomousZoneClimate(ClimateEntity):
    def __init__(self, ...):
        # ... existing init
        self._enabled = True  # New attribute
        self._last_valve_command_time = None
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "enabled": self._enabled,
            "satisfaction": self._satisfaction,
            # ... other attributes
        }
    
    async def async_added_to_hass(self):
        """Register event listeners."""
        await super().async_added_to_hass()
        
        # Existing temperature sensor listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.temp_sensor_id],
                self._handle_temperature_change,
            )
        )
        
        # NEW: Valve switch state listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.valve_switch_id],
                self._handle_valve_state_change,
            )
        )
    
    async def _handle_valve_state_change(self, event):
        """Handle valve switch state change (enable/disable zone)."""
        if (new_state := event.data.get("new_state")) is None:
            return
        
        old_state = event.data.get("old_state")
        if old_state is None:
            return
        
        # Check if state actually changed
        if new_state.state == old_state.state:
            return
        
        # Check if this change was made by us (zone)
        now = time.time()
        if (self._last_valve_command_time and 
            now - self._last_valve_command_time < 2.0):
            # Recent command by zone, ignore
            return
        
        # External valve state change detected
        new_valve_state = new_state.state == "on"
        
        if new_valve_state:
            # Valve turned ON -> Enable zone
            await self._handle_zone_enable()
        else:
            # Valve turned OFF -> Disable zone
            await self._handle_zone_disable()
    
    async def _handle_zone_disable(self):
        """Disable zone (exclude from calculations)."""
        _LOGGER.info(
            "Zone %s disabled via manual valve closure",
            self.zone_id
        )
        
        self._enabled = False
        self._valve_state = "closed"
        
        # Write to Redis
        await self._write_state_to_redis()
        
        # Trigger main coordinator update immediately
        coordinator = self.hass.data[DOMAIN]["main_coordinator"]
        await coordinator.async_request_refresh()
        
        # Update HA state
        self.async_write_ha_state()
    
    async def _handle_zone_enable(self):
        """Enable zone and immediately recalculate."""
        _LOGGER.info(
            "Zone %s enabled via manual valve opening",
            self.zone_id
        )
        
        self._enabled = True
        self._valve_state = "open"
        
        # Immediately recalculate satisfaction state
        self._calculate_satisfaction_state()
        
        # Immediately determine valve action
        desired_action = await self._determine_valve_action()
        
        # Execute valve action if needed
        if desired_action:
            await self._execute_valve_action(desired_action)
        
        # Write to Redis
        await self._write_state_to_redis()
        
        # Trigger main coordinator update immediately
        coordinator = self.hass.data[DOMAIN]["main_coordinator"]
        await coordinator.async_request_refresh()
        
        # Update HA state
        self.async_write_ha_state()
        
        _LOGGER.info(
            "Zone %s enabled, valve decision: %s",
            self.zone_id,
            desired_action or "no change"
        )
    
    async def _execute_valve_action(self, action: str):
        """Execute valve action with tracking."""
        # Track that we're commanding the valve
        self._last_valve_command_time = time.time()
        
        # ... existing valve execution logic
    
    async def _write_state_to_redis(self):
        """Write zone state to Redis."""
        state = {
            "zone_id": self.zone_id,
            "enabled": self._enabled,  # NEW field
            "current_temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "satisfaction": self._satisfaction,
            "valve_state": self._valve_state,
            # ... other fields
        }
        await self.redis_client.set_zone_state(self.zone_id, state)
```

**Key Points**:
- Event listener tracks valve switch state changes
- Distinguishes zone commands from external changes (timestamp tracking)
- Valve OFF → disable zone, exclude from calculations
- Valve ON → enable zone, immediate recalculation + valve decision
- Triggers main coordinator refresh immediately
- New `enabled` attribute visible in entity attributes

---

### 3. Algorithm Updates

**File**: `core/algorithms.py`

**Modify main target calculation**:
```python
def calculate_main_target_heating(zones, main_current_temp):
    """Calculate main target for heating mode."""
    # Filter for ENABLED zones only
    enabled_zones = [z for z in zones if z.get("enabled", True)]
    
    if not enabled_zones:
        # No enabled zones, return minimum safe target
        return main_current_temp
    
    # Categorize enabled zones
    underheated = [z for z in enabled_zones 
                   if z["satisfaction"] == "underheated"]
    satisfied = [z for z in enabled_zones 
                 if z["satisfaction"] == "satisfied"]
    overheated = [z for z in enabled_zones 
                  if z["satisfaction"] == "overheated"]
    
    # ... rest of existing logic using enabled_zones only
```

**Modify valve decision logic**:
```python
async def _determine_valve_action(self):
    """Determine valve action."""
    # Check if zone is enabled
    if not self._enabled:
        # Disabled zone - keep valve closed
        return None
    
    # ... existing logic for enabled zones
```

---

### 4. Safety Coordinator Updates

**File**: `coordinator.py` - `SafetyCoordinator`

**Modify**:
```python
async def _async_update_data(self):
    """Check minimum valves open (enabled zones only)."""
    zones = await self.redis_client.get_all_zones()
    
    # Count open valves in ENABLED zones only
    enabled_zones = [z for z in zones if z.get("enabled", True)]
    open_valves = [z for z in enabled_zones 
                   if z["valve_state"] in ["open", "opening"]]
    
    open_count = len(open_valves)
    min_required = self.config["min_valves_open"]
    
    if open_count < min_required:
        # Safety violation - force open fallback (must be enabled)
        fallback_zones = [z for z in enabled_zones if z.get("is_fallback")]
        # ... force open logic
```

**Key Point**: Only count enabled zones for minimum valve requirement.

---

## User Experience

### Scenario 1: User Changes Main Climate Target

```
User: Sets main climate to 28°C
      ↓
System: Detects change in < 100ms
      ↓
System: Immediately calculates correct target (23°C)
      ↓
System: Overrides back to 23°C
      ↓
System: Shows notification (optional):
        "Manual change overridden. Main target is automatically 
         calculated based on zone requirements."
      ↓
User: Sees target briefly at 28°C, then back to 23°C
User: Receives notification explaining why
```

**Result**: Clear that main target is auto-calculated, cannot be manually controlled.

---

### Scenario 2: User Closes Bedroom Valve

```
User: Turns switch.bedroom_valve OFF
      ↓
System: Detects change in < 100ms
      ↓
System: Disables bedroom zone
        - climate.bedroom shows "enabled: false" attribute
        - Valve closed
        - Excluded from calculations
      ↓
System: Recalculates main target (bedroom excluded)
      ↓
System: Other zones recalculate valve states
      ↓
User: Bedroom effectively "turned off"
      Room won't heat, won't affect other zones
```

**Result**: User has clear control via valve switch. Closing valve = turning off zone.

---

### Scenario 3: User Opens Bedroom Valve

```
User: Turns switch.bedroom_valve ON
      ↓
System: Detects change in < 100ms
      ↓
System: Enables bedroom zone
        - climate.bedroom shows "enabled: true" attribute
        - Immediately calculates satisfaction (e.g., underheated)
        - Determines valve should be OPEN
        - Keeps valve ON
      ↓
System: Recalculates main target (bedroom included)
      ↓
System: Other zones recalculate valve states
      ↓
User: Bedroom immediately active
      Room starts heating if needed
```

**Result**: Zone immediately active and participating in system.

---

## Edge Cases & Considerations

### Edge Case 1: Rapid Valve Toggling

**Scenario**: User rapidly toggles valve ON/OFF/ON/OFF

**Handling**:
- Timestamp tracking prevents double-processing own commands
- Each toggle triggers enable/disable cycle
- Main coordinator throttles updates (debounce)
- No system instability

**Mitigation**:
- Consider debouncing valve state changes (e.g., 2-second window)
- Log rapid toggles as warnings

---

### Edge Case 2: All Zones Disabled

**Scenario**: User disables all zones via valve switches

**Handling**:
- Main target calculation: No enabled zones → return safe minimum
- Safety coordinator: No enabled zones → skip enforcement
- Log warning: "All zones disabled, system inactive"

**Mitigation**:
- Send notification when last zone disabled
- Consider preventing last zone from being disabled (config option)

---

### Edge Case 3: Zone Disabled While Underheated

**Scenario**: Bedroom needs heat (20°C / 22°C), user disables it

**Handling**:
- Zone disabled immediately
- Main target recalculated (bedroom excluded)
- Main target may drop (no longer boosting for bedroom)
- Other zones adjust accordingly
- Bedroom temperature will drop over time

**Result**: User's explicit action respected. Room gets cold as intended.

---

### Edge Case 4: Main Climate Target Changed During Calculation

**Scenario**: Coordinator calculating target, user changes it simultaneously

**Handling**:
- Timestamp tracking detects own vs external changes
- If external change during calculation: triggers another refresh
- Eventual consistency achieved within 1-2 seconds

**Mitigation**:
- Lock/semaphore during coordinator update
- Queue external changes during calculation

---

### Edge Case 5: Zone Enabled But Immediately Overheated

**Scenario**: User enables bedroom, but main target is 25°C, bedroom target is 21°C

**Handling**:
```
T=0s    User enables bedroom (valve ON)
T=0.1s  Zone calculates: satisfied at 21°C
        Main target: 25°C (due to other zones)
        Hybrid logic tier 1: 25°C > 21.3°C → would overheat
        Decision: CLOSE valve immediately
T=0.2s  Valve closed by zone
        
Result: Zone enabled but valve closed (protecting from overheat)
```

**This is correct behavior**: Zone is enabled (participating) but valve closed for safety.

---

## Implementation Checklist

### Phase 1: Main Climate Target Override (3-4 hours)
- [ ] Add event listener in MainClimateCoordinator
- [ ] Implement timestamp tracking for coordinator updates
- [ ] Implement external change detection logic
- [ ] Add immediate coordinator refresh trigger
- [ ] Add notification on override (optional)
- [ ] Test: Manual change overridden within 1 second
- [ ] Test: Coordinator updates don't trigger false positives

### Phase 2: Valve State Change Listeners (4-5 hours)
- [ ] Add valve state event listener in AutonomousZoneClimate
- [ ] Implement timestamp tracking for zone valve commands
- [ ] Implement zone disable logic
- [ ] Implement zone enable + recalculation logic
- [ ] Add `enabled` attribute to zone entity
- [ ] Add `enabled` field to Redis state
- [ ] Test: Valve OFF disables zone immediately
- [ ] Test: Valve ON enables zone + recalculates immediately
- [ ] Test: Own valve commands don't trigger disable/enable

### Phase 3: Algorithm Updates (1-2 hours)
- [ ] Update main target calculation to filter enabled zones
- [ ] Update hybrid valve logic to check enabled status
- [ ] Update safety coordinator to only count enabled zones
- [ ] Test: Disabled zones excluded from calculations
- [ ] Test: Enabled zones included in calculations

### Phase 4: Testing & Edge Cases (2-3 hours)
- [ ] Test: All zones disabled scenario
- [ ] Test: Rapid valve toggling
- [ ] Test: Zone enabled but immediately closes (overheat protection)
- [ ] Test: Last zone disabled - system behavior
- [ ] Test: Coordinator + manual change race condition
- [ ] Load testing: Multiple rapid changes

### Total Estimated Effort: 10-14 hours

---

## Security Considerations

### 1. Notification Spam Prevention
**Risk**: User repeatedly changes main climate, gets spammed with notifications

**Mitigation**:
- Debounce notifications (max 1 per minute)
- Make notifications optional via config
- Use persistent notification (updates existing, not creates new)

### 2. Zone Disable Abuse
**Risk**: User or automation accidentally disables all zones

**Mitigation**:
- Log warnings when zones disabled
- Send notification when last zone disabled
- Optional config: `prevent_all_zones_disabled: true`
- Safety coordinator still monitors (force enable fallback if needed)

### 3. Timestamp Overflow
**Risk**: Timestamp comparison fails after long runtime

**Mitigation**:
- Use relative time differences, not absolute timestamps
- Reset tracking after long periods (> 1 hour)

### 4. Redis State Corruption
**Risk**: `enabled` field missing in Redis causes errors

**Mitigation**:
- Default to `enabled: true` if field missing
- Migration: Add `enabled: true` to all existing zones on startup
- Validation: Check field exists before using

---

## Testing Requirements

### Unit Tests

**Main Climate Override**:
- [ ] External change detected correctly
- [ ] Coordinator change ignored correctly
- [ ] Immediate refresh triggered
- [ ] Timestamp tracking works across multiple changes

**Zone Enable/Disable**:
- [ ] Valve OFF disables zone
- [ ] Valve ON enables zone
- [ ] Own commands ignored
- [ ] External commands processed
- [ ] Enabled zones participate in calculations
- [ ] Disabled zones excluded from calculations

### Integration Tests

**Scenarios**:
- [ ] User changes main target → overridden within 1s
- [ ] User closes valve → zone disabled, main target recalculated
- [ ] User opens valve → zone enabled, valve decision made
- [ ] All zones disabled → safe system state
- [ ] Rapid toggles → system stable

### End-to-End Tests

**User Workflows**:
- [ ] Morning: User opens bedroom valve → heating starts
- [ ] Day: User closes office valve → office disabled, other zones unaffected
- [ ] Evening: User tries to change main target → change reverted, notified
- [ ] Night: All zones disabled → system idle safely

---

## Documentation Updates

### User Documentation
- [ ] Explain main climate target is auto-calculated (cannot be manual)
- [ ] Explain valve switches control zone enable/disable
- [ ] Provide examples of disabling zones via valve switch
- [ ] Warning: Disabling all zones may stop heating

### Developer Documentation
- [ ] Document `enabled` attribute in zone entity
- [ ] Document timestamp tracking mechanism
- [ ] Document immediate refresh trigger
- [ ] Update architecture diagrams

### Configuration Documentation
- [ ] Optional: `notify_on_main_override: true/false`
- [ ] Optional: `prevent_all_zones_disabled: true/false`
- [ ] Note: No per-zone config needed (automatic behavior)

---

## Migration from Previous Analysis

**Previous recommendation** (Solution A2 + B1): 
- Temporary manual override mode
- Respect valve closures with config

**New requirement**: 
- Immediate override (no manual mode)
- Valve controls zone enable/disable

**Changes needed**:
- Remove manual override mode concept
- Remove per-zone `manual_valve_override` config
- Add zone `enabled` state
- Change valve listener behavior from "respect closure" to "disable zone"

**Backward compatibility**: N/A (no code exists yet, pure documentation)

---

## Recommendation: Proceed with Option A

**Rationale**:
1. ✅ Meets all new requirements exactly
2. ✅ Clear user mental model:
   - Main target = automatic (cannot change)
   - Valve switch = zone on/off control
3. ✅ No configuration complexity
4. ✅ Immediate response (< 1 second)
5. ✅ Safety maintained
6. ✅ Reasonable implementation effort (10-14 hours)

**Alternative**: Option C (configurable) if you want backward compatibility or flexibility, but adds complexity.

---

## Next Steps

**Status**: ✋ **AWAITING YOUR DECISION**

Please confirm:
1. ✅ Proceed with Option A (event-driven immediate override + zone enable/disable)?
2. 📢 Should we send notifications when main target is overridden?
3. 📢 Should we prevent all zones from being disabled (safety option)?
4. 🚀 Create detailed implementation plan & architecture docs?
5. 🛠️ Begin implementation?

---

## Summary

**What this solution provides**:
- ✅ Immediate main climate target override (< 1s, not 30s)
- ✅ Valve switch controls zone enable/disable
- ✅ Disabled zones excluded from all calculations
- ✅ Enabled zones immediately recalculate valve state
- ✅ Clear user mental model
- ✅ Safety maintained
- ✅ No configuration complexity

**Ready to implement**: Yes, solution is complete and detailed.

**Document Version**: 1.0  
**Created**: 2026-02-10  
**Status**: AWAITING USER APPROVAL
