# FINAL APPROVED SOLUTION - Implementation Ready

> ⚠️ **SUPERSEDED** — This document has been superseded by
> [`docs/COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md`](../COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)
> (v1.2), which is the **single source of truth** for all architecture decisions, code
> examples, and implementation specifications.  This file is preserved for historical
> reference only.
>
> Known bugs in this file that are corrected in the primary document:
> - B1 threshold uses `> 1s` (correct value is `> 2s`)
> - `_delayed_disable()` uses `asyncio.create_task()` (must be `hass.async_create_task()`)
> - `_get_available_fallback()` preference is inverted (see primary doc for correct logic)
> - `_get_available_fallback()` lacks an `IndexError` guard

---

## 🎉 Solution Approved

**Date**: 2026-02-11  
**Status**: ✅ **IMPLEMENTATION READY** (Updated with A1+A2 and B1+B2 combined)

---

## ✅ User's Decisions

### 1. Valve Switches
**Decision**: No separate valve switch entities needed
- Valve switches already exist (linked to zigbee devices)
- Component only tracks valve status
- User can see valve status on zone device detail
- User can manually control valves via zigbee app (outside component)
- **Implementation**: Read-only status display, no entity creation

### 2. Zone ON/OFF Control - **DUAL MECHANISM (A1 + A2 Combined)**
**Decision**: BOTH service-based AND event-driven control

**A1 - Service-Based Control**:
- User can call `climate.turn_on(zone)` / `climate.turn_off(zone)` services
- Explicit zone control via Home Assistant UI or automations
- **Implementation**: Climate entity with enable/disable capability

**A2 - Event-Driven Auto Control**:
- Valve switch state changes automatically enable/disable zone
- Valve OFF (ON→OFF) → Automatically disable zone
- Valve ON (OFF→ON) → Automatically enable zone + immediate recalculation
- **Implementation**: Event listener on valve switch state changes

**Combined Behavior**:
Both mechanisms work simultaneously. Zone can be controlled via:
1. Climate service calls (explicit user action)
2. Valve switch state changes (automatic detection)
3. Either method updates zone.enabled state
4. Either method triggers immediate zone state recalculation

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

### 6. Main Climate Target Override - **DUAL MECHANISM (B1 + B2 Combined)**
**Decision**: BOTH immediate event listener AND regular coordinator updates

**B1 - Immediate Event Listener Override**:
- Triggered ONLY when user manually changes main climate target temperature
- Response time: **< 1 second**
- Event listener detects change NOT from coordinator
- Immediately recalculates correct value and overrides back
- Sends notification explaining why change was reverted
- **Implementation**: Event listener on main climate target attribute with timestamp tracking

**B2 - Regular Coordinator Updates**:
- Normal coordinator cycle continues for regular operation
- Calculates and updates main climate target periodically
- Coordinator-initiated changes do NOT trigger B1 event listener
- **Implementation**: Existing coordinator pattern with timestamp marking

**Combined Behavior**:
```python
# Coordinator update (B2)
coordinator.set_target(calculated_value, timestamp=now())
# No event trigger, normal operation

# User manual change detected (B1)
if target_changed and not from_coordinator(change_time):
    # Immediate override < 1s
    coordinator.recalculate_and_override()
    notify_user("Manual change overridden - using calculated value")
```

**Timestamp Tracking**:
- Coordinator marks every update it makes with timestamp
- Event listener compares change timestamp with last coordinator update
- If timestamps don't match → external/manual change → trigger B1 override
- If timestamps match → coordinator change → ignore (B2 normal operation)

---

## 📋 Complete Solution Architecture

### Core Principles

1. **Dual Control Mechanisms**
   - Zone control: BOTH service calls (A1) AND valve events (A2)
   - Climate override: BOTH immediate events (B1) AND coordinator (B2)
   - Maximum flexibility with safety maintained

2. **Separation of Concerns**
   - System controls valves when zone is ON
   - User controls zones via Climate entity ON/OFF OR valve switch
   - Zone OFF = manual mode (system ignores valve)

3. **Immediate Responsiveness**
   - Manual climate changes overridden < 1s (B1)
   - Valve state changes trigger immediate zone recalc (A2)
   - Zone service calls trigger immediate recalc (A1)

4. **Safety First**
   - Fallback zones protected
   - Minimum valves always guaranteed
   - Smooth transitions with delayed disable

5. **Smart Timing**
   - Use fallback.valve_delay for delayed disable
   - Track valve state changes
   - Calculate remaining time if valve already opening

---

## 🏗️ System Components

### 1. Climate Entity (Zone) - With Dual Control (A1 + A2)

**Attributes**:
```python
class ZoneClimateEntity:
    enabled: bool  # ON/OFF state (controlled by A1 OR A2)
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
    
    # NEW: Event listener for valve switch (A2)
    valve_switch_listener: Optional[Callable]
```

**Services (A1 - Service-Based Control)**:
- `turn_on()` - Enable zone, resume system control
- `turn_off()` - Disable zone (with safety checks)
- `set_temperature()` - Set target temperature
- `cancel_pending_disable()` - Cancel delayed disable

**Event Listeners (A2 - Event-Driven Control)**:
- `_valve_switch_state_changed()` - Listens to valve switch state changes
  - Valve OFF → Calls `_auto_disable_zone()`
  - Valve ON → Calls `_auto_enable_zone()`
  - Both trigger immediate zone recalculation

**Attributes Exposed**:
- `enabled` - Zone ON/OFF state (updated by A1 OR A2)
- `valve_status` - Current valve status (read-only)
- `pending_disable` - Is delayed disable active
- `pending_disable_remaining` - Time remaining (seconds)
- `control_method` - Last control method used ("service" or "valve_event")

---

### 2. Main Climate Coordinator - With Dual Override (B1 + B2)

**Attributes**:
```python
class MainClimateCoordinator:
    main_climate_entity: str
    zones: List[ZoneClimateEntity]
    
    # NEW: Timestamp tracking for B1/B2 distinction
    last_coordinator_update: datetime
    last_target_value: float
    
    # NEW: Event listener for manual changes (B1)
    main_climate_listener: Optional[Callable]
```

**Coordinator Updates (B2 - Regular Operation)**:
```python
async def async_update_data(self):
    """Regular coordinator update cycle."""
    # Calculate correct main target
    calculated_target = self._calculate_main_target()
    
    # Update with timestamp marking
    self.last_coordinator_update = datetime.now()
    self.last_target_value = calculated_target
    
    # Set main climate target
    await self.hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": self.main_climate_entity,
            "temperature": calculated_target
        }
    )
    
    return calculated_target
```

**Event Listener (B1 - Immediate Override)**:
```python
async def _main_climate_target_changed(self, event):
    """Immediate override when user manually changes main climate target."""
    new_state = event.data.get("new_state")
    if not new_state:
        return
    
    new_target = new_state.attributes.get("temperature")
    change_time = event.time_fired
    
    # Check if this is an external/manual change
    time_diff = (change_time - self.last_coordinator_update).total_seconds()
    
    # If change occurred > 2s after last coordinator update, it's manual
    # (2s threshold accounts for event-processing delays; see primary doc §4.2.4)
    if time_diff > 2 and new_target != self.last_target_value:
        _LOGGER.warning(
            f"Manual main climate change detected: {new_target}°C. "
            f"Overriding to calculated value..."
        )
        
        # Immediate recalculation and override (< 1s)
        calculated_target = self._calculate_main_target()
        
        # Mark this as coordinator update to prevent event loop
        self.last_coordinator_update = datetime.now()
        self.last_target_value = calculated_target
        
        # Override back to calculated value
        await self.hass.services.async_call(
            "climate",
            "set_temperature",
            {
                "entity_id": self.main_climate_entity,
                "temperature": calculated_target
            }
        )
        
        # Notify user
        await self._send_notification(
            "Main Climate Override",
            f"Manual change to {new_target}°C was overridden. "
            f"System using calculated value: {calculated_target}°C based on zone requirements."
        )
```
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

### 3. Zone Enable/Disable Logic - Dual Mechanism (A1 + A2)

#### A1: Service-Based Control

```python
async def async_turn_off(self):
    """Disable zone with safety checks (A1 - Service call)."""
    
    # Log control method
    self.control_method = "service"
    
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

async def async_turn_on(self):
    """Enable zone (A1 - Service call)."""
    
    # Log control method
    self.control_method = "service"
    
    # Enable zone
    self.enabled = True
    
    # Immediately recalculate valve state
    await self._recalculate_valve_state()
    
    # Trigger coordinator update
    coordinator = self.hass.data[DOMAIN]["main_coordinator"]
    await coordinator.async_request_refresh()
    
    # Send notification
    await self._send_info_notification(
        f"{self.name} zone enabled",
        "System will now control valve automatically"
    )
```

#### A2: Event-Driven Auto Control

```python
async def async_added_to_hass(self):
    """Subscribe to valve switch state changes when entity added to hass."""
    
    # Subscribe to valve switch state changes (A2)
    @callback
    def valve_switch_state_changed(event):
        """Handle valve switch state changes (A2 - Event-driven)."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state or not old_state:
            return
        
        # Check if state actually changed
        if new_state.state == old_state.state:
            return
        
        # Log control method
        self.control_method = "valve_event"
        
        # Valve turned OFF -> Auto-disable zone
        if new_state.state == "off" and old_state.state == "on":
            _LOGGER.info(
                f"Valve switch {self.valve_switch} turned OFF. "
                f"Auto-disabling zone {self.name} (A2)"
            )
            # Use hass.async_create_task for callback context
            self.hass.async_create_task(self._auto_disable_zone())
        
        # Valve turned ON -> Auto-enable zone
        elif new_state.state == "on" and old_state.state == "off":
            _LOGGER.info(
                f"Valve switch {self.valve_switch} turned ON. "
                f"Auto-enabling zone {self.name} (A2)"
            )
            # Use hass.async_create_task for callback context
            self.hass.async_create_task(self._auto_enable_zone())
    
    # Register event listener
    self.valve_switch_listener = async_track_state_change_event(
        self.hass,
        [self.valve_switch],
        valve_switch_state_changed
    )

async def _auto_disable_zone(self):
    """Auto-disable zone when valve turned off (A2)."""
    
    # Same safety checks as service-based disable
    if self.is_fallback:
        enabled_fallbacks = count_enabled_fallback_zones()
        if enabled_fallbacks <= self.config.min_valves_open:
            await self._send_error_notification(
                "Cannot auto-disable fallback zone",
                f"{self.name} valve was turned off but zone is required "
                f"for minimum valve requirements. Please turn valve back on "
                f"or enable another fallback zone first."
            )
            # Try to turn valve back on
            await self.hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": self.valve_switch}
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
        
        await self._send_info_notification(
            f"{self.name} zone auto-disabled",
            "Zone disabled because valve was turned off (A2)"
        )

async def _auto_enable_zone(self):
    """Auto-enable zone when valve turned on (A2)."""
    
    # Enable zone
    self.enabled = True
    
    # Immediately recalculate valve state
    await self._recalculate_valve_state()
    
    # Trigger coordinator update
    coordinator = self.hass.data[DOMAIN]["main_coordinator"]
    await coordinator.async_request_refresh()
    
    await self._send_info_notification(
        f"{self.name} zone auto-enabled",
        "Zone enabled because valve was turned on (A2)"
    )

async def will_remove_from_hass(self):
    """Unsubscribe from events when entity removed."""
    if self.valve_switch_listener:
        self.valve_switch_listener()
```

---

### 4. Zone Disable Logic (Continued from A1/A2)

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
    
    # Create timer — MUST use hass.async_create_task() in HA callback context
    self.pending_disable_timer = self.hass.async_create_task(
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
    """Get an available fallback zone to open.
    
    Selection priority (see primary doc §3.2 for full rationale):
    1. Fallback already opening → benefits from remaining-time calculation.
    2. Fallback already fully open → already safe, no extra delay.
    3. Any other enabled fallback.
    4. If none enabled, enable the first configured fallback.
    
    Raises:
        RuntimeError: Raised immediately at function entry if no fallback zones
            are configured (i.e. `is_fallback=true` is not set on any zone).
    """
    
    # Get all fallback zones
    fallback_zones = [z for z in self.all_zones if z.is_fallback]
    
    if not fallback_zones:
        raise RuntimeError(
            "No fallback zones configured. "
            "At least one zone must have is_fallback=true."
        )
    
    # Prefer already enabled fallbacks
    enabled_fallbacks = [z for z in fallback_zones if z.enabled]
    if enabled_fallbacks:
        # Priority 1: already opening (remaining-time optimisation)
        for fb in enabled_fallbacks:
            if fb.valve_status == "opening":
                return fb
        # Priority 2: fully open
        for fb in enabled_fallbacks:
            if fb.valve_status == "open":
                return fb
        # Priority 3: any other enabled fallback (will start opening)
        return enabled_fallbacks[0]
    
    # No enabled fallbacks — enable the first configured one
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

### Phase 1: Main Climate Override with Dual Mechanism (B1 + B2) (4-5 hours)

**Tasks**:
- [ ] **B1: Event Listener for Manual Changes**
  - Add event listener for main climate target changes
  - Implement timestamp tracking (coordinator vs external)
  - Implement immediate override logic (< 1s)
  - Add notification on override
- [ ] **B2: Regular Coordinator Updates**
  - Mark coordinator updates with timestamps
  - Ensure coordinator updates don't trigger event listener
  - Maintain normal periodic update cycle

**Files**:
- `coordinator.py` - MainClimateCoordinator with timestamp tracking and event listener

**Tests**:
- Test: External change detected and overridden < 1s (B1)
- Test: Coordinator change ignored (B2)
- Test: Notification sent on manual override
- Test: Timestamp tracking distinguishes changes correctly

---

### Phase 2: Zone ON/OFF with Dual Control (A1 + A2) (8-9 hours)

**Tasks**:
- [ ] **A1: Service-Based Control**
  - Add `enabled` attribute to zone climate entity
  - Implement `turn_on()` service
  - Implement `turn_off()` service with safety checks
  - Add immediate recalculation on service calls
- [ ] **A2: Event-Driven Auto Control**
  - Add event listener for valve switch state changes
  - Implement auto-disable when valve turned OFF
  - Implement auto-enable when valve turned ON
  - Add safety checks for auto-disable (same as A1)
  - Subscribe/unsubscribe to events in lifecycle methods
- [ ] **Both Mechanisms**
  - Track control_method (service vs valve_event)
  - Ensure both trigger immediate recalculation
  - Add notifications for both mechanisms
- [ ] **Safety Features (for both A1 and A2)**
  - Implement fallback zone identification
  - Implement delayed disable logic
  - Implement valve state change tracking
  - Implement remaining time calculation
  - Add `cancel_pending_disable()` service
  - Add pending_disable state attributes

**Files**:
- `climate.py` - AutonomousZoneClimate with dual control
- `const.py` - Add constants

**Tests**:
- Test: Turn on zone via service (A1)
- Test: Turn off zone via service (A1)
- Test: Auto-enable when valve turned on (A2)
- Test: Auto-disable when valve turned off (A2)
- Test: Both mechanisms update enabled state correctly
- Test: Both mechanisms trigger recalculation
- Test: Control method tracked correctly
- Test: Safety checks work for both mechanisms
- Test: Delayed disable works for both mechanisms
- Test: Cancel delayed disable works

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

**Total**: 18-24 hours (increased from 15-20 due to dual mechanisms)

| Phase | Hours | Description |
|-------|-------|-------------|
| Phase 1 | 4-5 | Main climate override (B1 + B2) |
| Phase 2 | 8-9 | Zone ON/OFF (A1 + A2) with dual control |
| Phase 3 | 2-3 | Valve status tracking |
| Phase 4 | 1-2 | Algorithm updates |
| Phase 5 | 3-5 | Testing & integration (more tests needed) |

**Complexity Increase**: +3-4 hours due to:
- Dual zone control mechanisms (A1 + A2)
- Event listener implementation and testing
- Timestamp tracking for B1/B2 distinction
- Additional test coverage needed

---

## ✅ Implementation Readiness Checklist

- [x] **Architecture defined** - Complete with dual mechanisms
- [x] **User decisions finalized** - All 6 decisions confirmed (added #6 for B1+B2)
- [x] **Scenarios documented** - All scenarios with dual mechanisms
- [x] **Edge cases identified** - Covered including event loops
- [x] **Safety mechanisms designed** - Fallback protection for both A1 and A2
- [x] **Configuration schema defined** - Complete with validation
- [x] **Testing strategy defined** - Unit + integration for both mechanisms
- [x] **Notifications designed** - Error, warning, info for both mechanisms
- [x] **State management designed** - All states including control_method
- [x] **Timing logic designed** - Remaining time + immediate override
- [x] **Event listener design** - A2 valve events + B1 climate events

---

## 🔒 Security Considerations

1. **Configuration Validation**
   - Validate fallback count >= min_valves_open at startup
   - Prevent invalid configurations from loading

2. **Safety Enforcement**
   - Always enforce minimum valves open (for both A1 and A2)
   - Block fallback disable when needed (for both A1 and A2)
   - No bypass mechanisms

3. **State Integrity**
   - Track all state changes with timestamps
   - Validate state transitions
   - Clean up timers on errors
   - Prevent event loops with timestamp tracking (B1/B2)

4. **User Notifications**
   - Always notify on blocked actions (both mechanisms)
   - Always notify on delayed actions (both mechanisms)
   - Clear, actionable messages
   - Distinguish between A1 and A2, B1 and B2

5. **Event Listener Safety**
   - Prevent infinite loops between event listeners
   - Use hass.async_create_task() for callback context
   - Validate event data before processing
   - Unsubscribe on entity removal

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
- Users control via zigbee app OR system auto-control

### 5. Event Loop Prevention (B1/B2)

**CRITICAL: Prevent infinite loops between B1 and coordinator**:

```python
# Coordinator update (B2) - Mark timestamp
self.last_coordinator_update = datetime.now()
await set_temperature(calculated_value)

# Event listener (B1) - Check timestamp
if change_time - self.last_coordinator_update > 1s:
    # External change, override
    self.last_coordinator_update = datetime.now()  # Mark before override!
    await set_temperature(calculated_value)
```

### 6. Event Listener Context (A2)

**CRITICAL: Use hass.async_create_task() in callbacks**:

```python
@callback
def valve_switch_state_changed(event):
    # ✅ CORRECT
    self.hass.async_create_task(self._auto_disable_zone())
    
    # ❌ WRONG - Don't use asyncio.create_task()
    asyncio.create_task(self._auto_disable_zone())
```

### 7. Both Mechanisms Must Respect Safety

**Both A1 and A2 must perform same safety checks**:

```python
# A1 Service call
async def async_turn_off(self):
    if self.is_fallback and would_violate_minimum():
        return  # Block

# A2 Event-driven
async def _auto_disable_zone(self):
    if self.is_fallback and would_violate_minimum():
        await turn_valve_back_on()  # Try to fix
        return  # Block
```

---

## 📋 Questions Resolved

**All design decisions finalized** - 6 decisions total:
1. Valve switches: Read-only status ✅
2. Zone ON/OFF: **BOTH service (A1) AND event (A2)** ✅
3. Fallback zones: Multiple allowed ✅
4. Delayed disable: Cancellation allowed ✅
5. Fallback already open: Wait remaining time ✅
6. **Main climate override: BOTH immediate event (B1) AND coordinator (B2)** ✅

---

## ✅ STATUS: IMPLEMENTATION READY

All requirements defined, all decisions made, dual mechanisms specified, ready to implement!

---

**Document Version**: 3.0 (Final Approved with A1+A2 and B1+B2)  
**Created**: 2026-02-10  
**Updated**: 2026-02-11 (Added dual mechanisms)  
**Status**: ✅ **IMPLEMENTATION READY**  
**Approved By**: User  
**Ready to Implement**: YES
