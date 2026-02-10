# FINAL APPROVED SOLUTION - Implementation Ready

## 🎉 Solution Approved

**Date**: 2026-02-10  
**Status**: ✅ **IMPLEMENTATION READY**

---

## ✅ User's Decisions

### 1. Valve Switches
**Decision**: No separate valve switch entities needed
- Valve switches already exist (linked to zigbee devices)
- Component only tracks valve status
- User can see valve status on zone device detail
- User can manually control valves via zigbee app (outside component)
- **Implementation**: Read-only status display, no entity creation

### 2. Zone ON/OFF Control
**Decision**: Via Climate entity
- Use climate entity turn_on/turn_off services
- No separate switch entity needed
- **Implementation**: Climate entity with enable/disable capability

### 3. Fallback Zones
**Decision**: Multiple fallback zones allowed
- Can configure MORE fallback zones than minimum valve open requirement
- Must configure AT LEAST as many as minimum valve open
- Example: min_valves_open = 1, can have 2+ fallback zones
- **Implementation**: Configuration validation + multiple fallback support

### 4. Delayed Disable Cancellation
**Decision**: Allow cancellation
- User can cancel pending zone disable
- When cancelled, **immediately recalculate valve states**
- **Implementation**: Cancellation mechanism + immediate recalculation trigger

### 5. Fallback Already Open
**Decision**: Wait for remaining time
- Track when valve state was changed
- Calculate remaining time from valve_delay
- Wait only for remaining time (not full delay again)
- **Implementation**: Track valve state change timestamps + remaining time calculation

---

## 📋 Complete Solution Architecture

### Core Principles

1. **Separation of Concerns**
   - System controls valves when zone is ON
   - User controls zones via Climate entity ON/OFF
   - Zone OFF = manual mode (system ignores valve)

2. **Safety First**
   - Fallback zones protected
   - Minimum valves always guaranteed
   - Smooth transitions with delayed disable

3. **Smart Timing**
   - Use fallback.valve_delay for delayed disable
   - Track valve state changes
   - Calculate remaining time if valve already opening

---

## 🏗️ System Components

### 1. Climate Entity (Zone)

**Attributes**:
```python
class ZoneClimateEntity:
    enabled: bool  # ON/OFF state
    current_temperature: float
    target_temperature: float
    hvac_mode: str  # heat, cool, off
    
    # Status only (not controllable via entity)
    valve_status: str  # open, closed, opening, closing
    
    # Delayed disable state
    pending_disable: bool
    pending_disable_timer: Optional[asyncio.Task]
    pending_disable_expires_at: Optional[datetime]
    pending_disable_fallback_zone: Optional[str]
    
    # Valve state tracking
    valve_state_changed_at: Optional[datetime]
```

**Services**:
- `turn_on()` - Enable zone, resume system control
- `turn_off()` - Disable zone (with safety checks)
- `set_temperature()` - Set target temperature
- `cancel_pending_disable()` - Cancel delayed disable (NEW)

**Attributes Exposed**:
- `enabled` - Zone ON/OFF state
- `valve_status` - Current valve status (read-only)
- `pending_disable` - Is delayed disable active
- `pending_disable_remaining` - Time remaining (seconds)

---

### 2. Configuration Schema

```yaml
multizone_climate:
  main_climate_entity: climate.main_thermostat
  min_valves_open: 1  # Minimum valves that must be open
  
  zones:
    bedroom:
      name: Bedroom
      climate_entity: climate.bedroom  # This component creates this
      temperature_sensor: sensor.bedroom_temp
      valve_switch: switch.bedroom_valve  # External (zigbee)
      valve_delay: 120  # seconds (time for valve to fully open)
      is_fallback: true  # Can be multiple fallbacks
      
    kitchen:
      name: Kitchen
      climate_entity: climate.kitchen
      temperature_sensor: sensor.kitchen_temp
      valve_switch: switch.kitchen_valve
      valve_delay: 180
      is_fallback: true  # Multiple fallbacks allowed
      
    living_room:
      name: Living Room
      climate_entity: climate.living_room
      temperature_sensor: sensor.living_temp
      valve_switch: switch.living_valve
      valve_delay: 120
      is_fallback: false
```

**Validation Rules**:
- `count(is_fallback=true) >= min_valves_open`
- All valve_switch entities must exist
- All temperature_sensor entities must exist

---

### 3. Zone Disable Logic (Enhanced)

```python
async def async_turn_off(self):
    """Disable zone with safety checks."""
    
    # Check if this is a fallback zone
    if self.is_fallback:
        enabled_fallbacks = count_enabled_fallback_zones()
        if enabled_fallbacks <= self.config.min_valves_open:
            # Cannot disable - would violate minimum
            await self._send_error_notification(
                "Cannot disable fallback zone",
                f"{self.name} is required for minimum valve requirements"
            )
            return
    
    # Check if this is the last open valve
    open_valves = count_open_valves()
    if open_valves == 1 and self.valve_status in ["open", "opening"]:
        # Need to open fallback first
        await self._delayed_disable()
    else:
        # Safe to disable immediately
        await self._immediate_disable()

async def _delayed_disable(self):
    """Delayed disable when last valve."""
    
    # Find a fallback zone to open
    fallback_zone = self._get_available_fallback()
    
    # Open fallback valve
    await fallback_zone.open_valve()
    
    # Calculate delay
    delay = await self._calculate_remaining_delay(fallback_zone)
    
    # Schedule delayed disable
    self.pending_disable = True
    self.pending_disable_fallback_zone = fallback_zone.id
    self.pending_disable_expires_at = datetime.now() + timedelta(seconds=delay)
    
    # Send warning notification
    await self._send_warning_notification(
        "Zone disable delayed",
        f"{self.name} will be disabled in {delay}s after {fallback_zone.name} valve opens"
    )
    
    # Create timer
    self.pending_disable_timer = asyncio.create_task(
        self._execute_delayed_disable(delay)
    )

async def _calculate_remaining_delay(self, fallback_zone):
    """Calculate remaining delay based on when valve started opening."""
    
    # Get fallback zone's valve delay
    full_delay = fallback_zone.valve_delay
    
    # Check when fallback valve state changed
    if fallback_zone.valve_state_changed_at:
        elapsed = (datetime.now() - fallback_zone.valve_state_changed_at).total_seconds()
        remaining = max(0, full_delay - elapsed)
        
        _LOGGER.info(
            f"Fallback {fallback_zone.name} already opening for {elapsed}s, "
            f"waiting {remaining}s more (of {full_delay}s total)"
        )
        
        return remaining
    else:
        # Valve just started opening
        fallback_zone.valve_state_changed_at = datetime.now()
        return full_delay

async def _execute_delayed_disable(self, delay):
    """Execute disable after delay."""
    await asyncio.sleep(delay)
    
    # Check if cancelled
    if not self.pending_disable:
        return
    
    # Execute disable
    await self._immediate_disable()
    
    # Clear pending state
    self.pending_disable = False
    self.pending_disable_timer = None
    self.pending_disable_expires_at = None
    
    # Send info notification
    await self._send_info_notification(
        f"{self.name} zone disabled",
        f"Fallback zone ({self.pending_disable_fallback_zone}) is now active"
    )
    
    self.pending_disable_fallback_zone = None

async def cancel_pending_disable(self):
    """Cancel pending zone disable."""
    
    if not self.pending_disable:
        return
    
    # Cancel timer
    if self.pending_disable_timer:
        self.pending_disable_timer.cancel()
    
    # Clear state
    self.pending_disable = False
    self.pending_disable_timer = None
    self.pending_disable_expires_at = None
    self.pending_disable_fallback_zone = None
    
    # Send info notification
    await self._send_info_notification(
        "Zone disable cancelled",
        f"{self.name} will remain enabled"
    )
    
    # IMPORTANT: Immediately recalculate valve states
    await self._recalculate_valve_state()
    
    # Trigger coordinator update
    coordinator = self.hass.data[DOMAIN]["main_coordinator"]
    await coordinator.async_request_refresh()
```

---

### 4. Valve State Tracking

```python
async def _update_valve_status(self, new_status):
    """Update valve status and track state changes."""
    
    old_status = self.valve_status
    self.valve_status = new_status
    
    # Track when valve state changed to "opening"
    if old_status != "opening" and new_status == "opening":
        self.valve_state_changed_at = datetime.now()
        _LOGGER.debug(
            f"{self.name} valve started opening at {self.valve_state_changed_at}"
        )
    
    # Clear timestamp when valve reaches final state
    if new_status in ["open", "closed"]:
        if self.valve_state_changed_at:
            duration = (datetime.now() - self.valve_state_changed_at).total_seconds()
            _LOGGER.debug(
                f"{self.name} valve reached {new_status} after {duration}s"
            )
        self.valve_state_changed_at = None
```

---

### 5. Fallback Zone Management

```python
def _get_available_fallback(self):
    """Get an available fallback zone to open."""
    
    # Get all fallback zones
    fallback_zones = [z for z in self.all_zones if z.is_fallback]
    
    # Prefer already enabled fallbacks
    enabled_fallbacks = [z for z in fallback_zones if z.enabled]
    if enabled_fallbacks:
        # Prefer one that's not already open
        for fb in enabled_fallbacks:
            if fb.valve_status not in ["open", "opening"]:
                return fb
        # All enabled fallbacks are open, return first
        return enabled_fallbacks[0]
    
    # No enabled fallbacks, enable the first one
    fallback = fallback_zones[0]
    fallback.enabled = True
    return fallback

def count_enabled_fallback_zones(self):
    """Count how many fallback zones are currently enabled."""
    return sum(1 for z in self.all_zones if z.is_fallback and z.enabled)

def validate_fallback_configuration(self):
    """Validate fallback configuration at startup."""
    
    fallback_count = sum(1 for z in self.all_zones if z.is_fallback)
    min_required = self.config.min_valves_open
    
    if fallback_count < min_required:
        raise ConfigurationError(
            f"At least {min_required} fallback zones required "
            f"(configured: {fallback_count})"
        )
    
    _LOGGER.info(
        f"Fallback configuration valid: {fallback_count} fallback zones, "
        f"minimum required: {min_required}"
    )
```

---

## 📊 Complete Scenario Flows

### Scenario 1: Normal Zone Disable (Not Last Valve)

```
Initial: Kitchen (fallback, OPEN), Bedroom (OPEN), Living (OPEN)
User: Turns bedroom OFF

T=0s    User calls climate.turn_off(bedroom)
T=0.1s  Check: Is bedroom fallback? NO
T=0.1s  Check: Is bedroom last open valve? NO (kitchen, living still open)
T=0.1s  Decision: IMMEDIATE DISABLE ✓
T=0.2s  Bedroom disabled, excluded from calculations
T=0.2s  Info notification: "Bedroom zone disabled"

Result: Immediate, simple
```

---

### Scenario 2: Delayed Disable (Last Valve, Fallback Not Open)

```
Initial: Kitchen (fallback, CLOSED), Bedroom (OPEN, only one!)
Config: kitchen.valve_delay = 180s
User: Turns bedroom OFF

T=0s    User calls climate.turn_off(bedroom)
T=0.1s  Check: Is bedroom fallback? NO
T=0.1s  Check: Is bedroom last open valve? YES
T=0.2s  Open kitchen (fallback) valve
T=0.2s  Kitchen.valve_state_changed_at = now
T=0.3s  Calculate delay: kitchen.valve_delay = 180s, elapsed = 0s, remaining = 180s
T=0.3s  Schedule delayed disable (180s)
T=0.3s  Warning notification: "Bedroom will disable in 3:00 minutes..."
T=0.3s  bedroom.pending_disable = True

T=3min  Timer expires
T=3min  Execute bedroom disable
T=3min  bedroom.pending_disable = False
T=3min  Info notification: "Bedroom disabled, kitchen active"

Result: Safe transition, fallback ready
```

---

### Scenario 3: Delayed Disable (Last Valve, Fallback Already Opening)

```
Initial: Kitchen (fallback, OPENING since 60s ago), Bedroom (OPEN, only one!)
Config: kitchen.valve_delay = 180s
User: Turns bedroom OFF

T=0s    User calls climate.turn_off(bedroom)
T=0.1s  Check: Is bedroom last open valve? YES
T=0.2s  Get kitchen (already opening)
T=0.3s  Calculate delay:
        - kitchen.valve_delay = 180s
        - kitchen.valve_state_changed_at = 60s ago
        - elapsed = 60s
        - remaining = 180 - 60 = 120s
T=0.3s  Schedule delayed disable (120s) ← Only remaining time!
T=0.3s  Warning notification: "Bedroom will disable in 2:00 minutes..."

T=2min  Timer expires (not 3min, only remaining!)
T=2min  Execute bedroom disable
T=2min  Info notification: "Bedroom disabled"

Result: Efficient, waits only necessary time
```

---

### Scenario 4: Cancel Delayed Disable

```
Initial: Kitchen (fallback, OPENING), Bedroom (PENDING_DISABLE, 90s remaining)
User: Cancels bedroom disable

T=0s    User calls climate.cancel_pending_disable(bedroom)
T=0.1s  Cancel timer
T=0.1s  bedroom.pending_disable = False
T=0.2s  Info notification: "Zone disable cancelled"
T=0.3s  IMMEDIATELY recalculate bedroom valve state
        - Current: 20°C, Target: 21°C → UNDERHEATED
        - Decision: OPEN
        - Execute: Open bedroom valve
T=0.4s  Trigger coordinator update
T=0.5s  Main target recalculated (bedroom included)

Result: Cancellation works, immediate recalculation
```

---

### Scenario 5: Blocked Disable (Fallback, Last One)

```
Initial: Kitchen (fallback, OPEN, only enabled fallback)
Config: min_valves_open = 1
User: Turns kitchen OFF

T=0s    User calls climate.turn_off(kitchen)
T=0.1s  Check: Is kitchen fallback? YES
T=0.1s  Count enabled fallbacks: 1
T=0.1s  Check: 1 <= min_valves_open (1)? YES → VIOLATION
T=0.1s  Decision: BLOCK ✓
T=0.2s  Error notification: "Cannot disable fallback zone..."

Result: Safety maintained, clear error
```

---

## 🔧 Implementation Phases

### Phase 1: Main Climate Override (3-4 hours)

**Tasks**:
- [ ] Add event listener for main climate target changes
- [ ] Implement timestamp tracking (coordinator vs external)
- [ ] Implement immediate override logic
- [ ] Add notification on override

**Files**:
- `coordinator.py` - MainClimateCoordinator

**Tests**:
- Test: External change detected and overridden
- Test: Coordinator change ignored
- Test: Notification sent

---

### Phase 2: Zone ON/OFF Control (6-7 hours)

**Tasks**:
- [ ] Add `enabled` attribute to zone climate entity
- [ ] Implement `turn_on()` service
- [ ] Implement `turn_off()` service with safety checks
- [ ] Implement fallback zone identification
- [ ] Implement delayed disable logic
- [ ] Implement valve state change tracking
- [ ] Implement remaining time calculation
- [ ] Add `cancel_pending_disable()` service
- [ ] Add pending_disable state attributes
- [ ] Add notifications (error, warning, info)

**Files**:
- `climate.py` - AutonomousZoneClimate
- `const.py` - Add constants

**Tests**:
- Test: Turn on zone (immediate enable)
- Test: Turn off zone (not last valve, immediate)
- Test: Turn off zone (last valve, delayed)
- Test: Turn off zone (fallback already opening, remaining time)
- Test: Cancel delayed disable
- Test: Block fallback disable

---

### Phase 3: Valve Status Tracking (2-3 hours)

**Tasks**:
- [ ] Track valve switch state (read-only)
- [ ] Update valve_status attribute
- [ ] Track valve_state_changed_at timestamps
- [ ] Display valve status in zone device detail
- [ ] No entity creation (use external zigbee switches)

**Files**:
- `climate.py` - Valve status tracking
- `device.py` - Device info display

**Tests**:
- Test: Valve status tracked correctly
- Test: Timestamps recorded on state change
- Test: Valve status displayed in device detail

---

### Phase 4: Algorithm Updates (1-2 hours)

**Tasks**:
- [ ] Filter enabled zones in main target calculation
- [ ] Filter enabled zones in hybrid valve logic
- [ ] Update safety coordinator to count enabled fallback zones
- [ ] Validate fallback configuration at startup

**Files**:
- `core/algorithms.py`
- `core/valve_control.py`
- `coordinator.py` - SafetyCoordinator
- `config_flow.py` - Validation

**Tests**:
- Test: Disabled zones excluded from calculations
- Test: Enabled zones included
- Test: Fallback count validation

---

### Phase 5: Testing & Integration (3-4 hours)

**Tasks**:
- [ ] Write unit tests for all scenarios
- [ ] Write integration tests
- [ ] Manual testing in Home Assistant
- [ ] Documentation updates
- [ ] README updates

**Tests**:
- All 5 scenarios from above
- Edge cases (rapid enable/disable, multiple zones)
- Configuration validation
- Notification delivery

---

## 🎯 Total Implementation Estimate

**Total**: 15-20 hours

| Phase | Hours | Description |
|-------|-------|-------------|
| Phase 1 | 3-4 | Main climate override |
| Phase 2 | 6-7 | Zone ON/OFF + delayed disable |
| Phase 3 | 2-3 | Valve status tracking |
| Phase 4 | 1-2 | Algorithm updates |
| Phase 5 | 3-4 | Testing & integration |

---

## ✅ Implementation Readiness Checklist

- [x] **Architecture defined** - Complete
- [x] **User decisions finalized** - All 5 decisions confirmed
- [x] **Scenarios documented** - All 5 scenarios detailed
- [x] **Edge cases identified** - Covered
- [x] **Safety mechanisms designed** - Fallback protection
- [x] **Configuration schema defined** - Complete with validation
- [x] **Testing strategy defined** - Unit + integration
- [x] **Notifications designed** - Error, warning, info
- [x] **State management designed** - All states defined
- [x] **Timing logic designed** - Remaining time calculation

---

## 🔒 Security Considerations

1. **Configuration Validation**
   - Validate fallback count >= min_valves_open at startup
   - Prevent invalid configurations from loading

2. **Safety Enforcement**
   - Always enforce minimum valves open
   - Block fallback disable when needed
   - No bypass mechanisms

3. **State Integrity**
   - Track all state changes with timestamps
   - Validate state transitions
   - Clean up timers on errors

4. **User Notifications**
   - Always notify on blocked actions
   - Always notify on delayed actions
   - Clear, actionable messages

---

## 📝 Critical Implementation Notes

### 1. Valve Delay Selection

**ALWAYS use the delay of the valve being OPENED**:

```python
# ✅ CORRECT
delay = fallback_zone.valve_delay  # When opening fallback

# ❌ WRONG
delay = zone_being_disabled.valve_delay  # NO!
```

### 2. Remaining Time Calculation

**Track when valves start opening, calculate remaining time**:

```python
# When valve starts opening
zone.valve_state_changed_at = datetime.now()

# When scheduling delay
elapsed = (now - zone.valve_state_changed_at).total_seconds()
remaining = max(0, zone.valve_delay - elapsed)
```

### 3. Cancel Triggers Recalculation

**When delayed disable is cancelled, IMMEDIATELY recalculate**:

```python
await self.cancel_pending_disable()
await self._recalculate_valve_state()  # ← CRITICAL!
await coordinator.async_request_refresh()
```

### 4. No Valve Switch Entities

**Component does NOT create valve switch entities**:
- Valves are external (zigbee)
- Component only tracks status (read-only)
- Display status in zone device detail
- Users control via zigbee app

---

## 📋 Questions Resolved

**No remaining questions** - All design decisions finalized by user.

---

## ✅ STATUS: IMPLEMENTATION READY

All requirements defined, all decisions made, ready to implement!

---

**Document Version**: 2.0 (Final Approved)  
**Created**: 2026-02-10  
**Status**: ✅ **IMPLEMENTATION READY**  
**Approved By**: User  
**Ready to Implement**: YES
