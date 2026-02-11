# Event Listeners and Triggers - Complete Reference

## Overview

This document describes **all event listeners** in the Fully Autonomous Zones architecture and the **exact sequence of actions** that occur when each event triggers.

---

## Event Listeners Table

| Event Source | Listener Owner | Event Type | Trigger Condition | Actions Triggered | Related Components | Notes |
|--------------|---------------|------------|-------------------|-------------------|-------------------|-------|
| **Zone Temperature Sensor** | `AutonomousZoneClimate` | `state_changed` | Temperature sensor value changes | 1. Validate event data<br>2. Extract new temperature<br>3. Calculate satisfaction state<br>4. Determine valve action (hybrid logic)<br>5. Execute valve action (if needed)<br>6. Write state to Redis | `SatisfactionCalculator`<br>`HybridValveController`<br>`ValveManager`<br>`RedisClient` | **Primary autonomous trigger** - drives all zone behavior |
| **Main Climate Temperature** | `MainClimateCoordinator` | `state_changed` (indirect via periodic update) | Main climate current_temperature attribute changes | 1. Extract new current temp<br>2. Trigger main target recalculation<br>3. Update Redis with new main state | `RedisClient` | Not direct listener - polled via coordinator |
| **Main Climate Target** | None (calculated) | N/A - Computed value | Main target calculated by coordinator | 1. Zones read from Redis when making decisions<br>2. Used in hybrid valve logic | `HybridValveController` | Passive - zones pull when needed |
| **Valve Switch State** | None (zones monitor indirectly) | N/A - Queried when needed | Valve switch turns on/off | 1. Zone queries state before actions<br>2. Updates internal valve_state<br>3. Writes to Redis | `ValveManager`<br>`RedisClient` | Reactive monitoring, not event-driven |
| **Zone Target Temperature Change** | `AutonomousZoneClimate` | `async_set_temperature` service call | User changes zone target via UI/service | 1. Update internal target_temperature<br>2. Write to Redis<br>3. Trigger re-evaluation (simulate temp change event)<br>4. Recalculate satisfaction<br>5. Determine valve action<br>6. Execute if needed | `SatisfactionCalculator`<br>`HybridValveController` | Service call, not state_changed event |
| **Timer (Main Coordinator)** | `MainClimateCoordinator` | Periodic timer | Every 30 seconds (configurable) | 1. Get all zones from Redis<br>2. Get main climate current temp<br>3. Calculate new main target<br>4. Write main state to Redis<br>5. Update main climate entity | `RedisClient` | Background coordination only |
| **Timer (Safety Coordinator)** | `SafetyCoordinator` | Periodic timer | Every 60 seconds (configurable) | 1. Get all zones from Redis<br>2. Count open valves<br>3. If < minimum: force open fallback<br>4. Log safety status | `RedisClient`<br>`ValveManager` | Safety backup mechanism |
| **Integration Reload** | All components | `async_added_to_hass` | Component loaded/reloaded | 1. Register event listeners<br>2. Initialize state from entities<br>3. Write initial state to Redis | All components | Initialization only |
| **Home Assistant Shutdown** | All components | `async_will_remove_from_hass` | HA stopping or integration removed | 1. Unregister event listeners<br>2. Cancel pending tasks<br>3. Cleanup resources | All components | Cleanup only |

---

## Detailed Event Flow Diagrams

### Event 1: Zone Temperature Sensor Change (Primary Event)

**Trigger**: `sensor.bedroom_temperature` changes from 20.9°C to 21.0°C

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: state_changed(sensor.bedroom_temperature)                │
│   old_state: 20.9°C                                             │
│   new_state: 21.0°C                                             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LISTENER: AutonomousZoneClimate._handle_temperature_change()    │
│   Registered via: async_track_state_change_event()              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Validate Event                                          │
│   ✓ Check: new_state is not None                               │
│   ✓ Check: old_state.state != new_state.state (actually changed)│
│   ✓ Extract: new_temp = float(new_state.state)                 │
│   ❌ If validation fails: return (ignore event)                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Update Internal State                                   │
│   old_temp = self._current_temperature (20.9)                   │
│   self._current_temperature = 21.0                              │
│   Log: "Zone bedroom: Temperature changed 20.9°C → 21.0°C"     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Calculate Satisfaction State                            │
│   Component: SatisfactionCalculator                             │
│   Input:                                                         │
│     - current_temp: 21.0                                        │
│     - target_temp: 21.0 (from self._target_temperature)        │
│     - previous_satisfaction: "underheated"                      │
│   Logic:                                                         │
│     - underheated_threshold = 21.0 - 0.0 = 21.0                │
│     - overheated_threshold = 21.0 + 0.3 = 21.3                 │
│     - Current 21.0 not < 21.0 (not underheated)                │
│     - Current 21.0 not > 21.3 (not overheated)                 │
│     - Was underheated, now at target                           │
│     - Must reach target + epsilon (21.1) to become satisfied   │
│   Output: "underheated" (still underheated due to hysteresis)  │
│   self._satisfaction = "underheated"                            │
│   Log: "Zone bedroom: Satisfaction remains underheated"        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Determine Valve Action                                  │
│   Method: self._determine_valve_action()                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4a: Check Valve Lock                                       │
│   time_since_last_action = now - self._last_valve_action_time  │
│   If < valve_delay (120s): return None (valve locked)          │
│   ✓ Valve not locked, continue                                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4b: Get Current Valve State                                │
│   valve_state = hass.states.get("switch.bedroom_valve")        │
│   current_valve_state = "open" if state == "on" else "closed"  │
│   Result: "closed" (assume valve was closed)                    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4c: Get Main Climate Target from Redis                     │
│   main_state = await redis_client.get_main_climate_state()     │
│   main_target = main_state["target_temperature"]               │
│   Result: 23.5°C                                                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4d: Get Underheated Zones from Redis                       │
│   all_zones = await redis_client.get_all_zones()               │
│   underheated = [z for z in all_zones                          │
│                  if z["satisfaction"] == "underheated"]         │
│   Result: [{"zone_id": "bedroom", "deficit": 0.0},             │
│            {"zone_id": "kitchen", "deficit": 2.0}]             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4e: Apply Hybrid Controller Logic                          │
│   Component: HybridValveController                              │
│   Input:                                                         │
│     - satisfaction: "underheated"                               │
│     - zone_target: 21.0                                         │
│     - upper_offset: 0.3                                         │
│     - main_target_temp: 23.5                                    │
│     - underheated_zones: [...kitchen, bedroom...]              │
│   Logic:                                                         │
│     - satisfaction == "underheated" → ALWAYS OPEN               │
│   Output: "open"                                                │
│   Log: "Hybrid decision: open (underheated zone)"              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4f: Check if State Change Needed                           │
│   desired_action: "open"                                        │
│   current_valve_state: "closed"                                 │
│   "open" != "closed" → Yes, action needed                       │
│   Return: "open"                                                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Execute Valve Action                                    │
│   Method: self._execute_valve_action("open")                    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5a: Safety Check (if closing)                              │
│   Action is "open", skip safety check                           │
│   (Safety check only for "close" actions)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5b: Execute via Valve Manager                              │
│   Component: ValveManager                                       │
│   await valve_manager.execute_action("open", "bedroom")         │
│   ├─ Call service: switch.turn_on                              │
│   │    entity_id: switch.bedroom_valve                          │
│   └─ Result: success=True                                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5c: Update Internal State                                  │
│   self._valve_state = "opening"                                 │
│   self._last_valve_action_time = time.time()                    │
│   Log: "Zone bedroom: Valve action 'open' executed"            │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Write State to Redis                                    │
│   Method: self._write_state_to_redis()                          │
│   state = {                                                      │
│     "zone_id": "bedroom",                                       │
│     "current_temperature": 21.0,                                │
│     "target_temperature": 21.0,                                 │
│     "satisfaction": "underheated",                              │
│     "valve_state": "opening",                                   │
│     "is_fallback": false,                                       │
│     "enabled": true,                                            │
│     "updated_at": 1707565800.0                                  │
│   }                                                              │
│   await redis_client.set_zone_state("bedroom", state)          │
│   Log: "Zone bedroom: State written to Redis"                  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ COMPLETE: Event handled in ~50-100ms                            │
│   Zone now waiting for next temperature change event            │
└─────────────────────────────────────────────────────────────────┘
```

---

### Event 2: Zone Temperature Sensor Change (Satisfied Zone with Underheated Zones)

**Trigger**: `sensor.bedroom_temperature` changes, bedroom is satisfied, kitchen is underheated

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: state_changed(sensor.bedroom_temperature)                │
│   Current bedroom: 21.0°C (satisfied)                           │
│   Kitchen: 22.0°C / 24.0°C (underheated, deficit 2°C)          │
│   Main target: 23.0 + 2.0 = 25.0°C                             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
[Steps 1-3: Same validation and satisfaction calculation]
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Hybrid Controller Logic (CRITICAL PATH)                 │
│   Input:                                                         │
│     - satisfaction: "satisfied"                                 │
│     - zone_target: 21.0                                         │
│     - upper_offset: 0.3                                         │
│     - main_target_temp: 25.0                                    │
│     - underheated_zones: [{"zone_id": "kitchen", "deficit": 2.0}]│
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ TIER 1: Temperature Safety Check                                │
│   overheat_threshold = 21.0 + 0.3 = 21.3°C                     │
│   main_target (25.0) > overheat_threshold (21.3)? YES          │
│   Decision: CLOSE (would overheat)                              │
│   Log: "TIER 1: Closing valve. Main 25.0°C > threshold 21.3°C" │
│   Output: "close"                                               │
│   (Tier 2 not evaluated)                                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Execute Valve Close                                     │
│   Safety check: Can we close this valve?                        │
│   ├─ Count open valves: 2 (kitchen + bedroom)                  │
│   ├─ Min required: 1                                            │
│   ├─ After close: 1 remaining                                   │
│   └─ OK to close ✓                                              │
│   Execute: switch.turn_off(switch.bedroom_valve)               │
│   Result: Bedroom valve CLOSED, kitchen continues heating       │
└─────────────────────────────────────────────────────────────────┘
```

---

### Event 3: Main Climate Coordinator Timer

**Trigger**: Periodic timer (every 30 seconds)

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: Timer tick (30 seconds elapsed)                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LISTENER: MainClimateCoordinator._async_update_data()           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Get All Zones from Redis                                │
│   zones = await redis_client.get_all_zones()                    │
│   Result: [                                                      │
│     {zone_id: "bedroom", satisfaction: "satisfied", ...},       │
│     {zone_id: "kitchen", satisfaction: "underheated", ...}      │
│   ]                                                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Get Main Climate Current Temperature                    │
│   main_state = hass.states.get("climate.main_thermostat")      │
│   main_current = float(main_state.attributes["current_temperature"])│
│   Result: 23.0°C                                                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Calculate Main Target Temperature                       │
│   Method: _calculate_main_target_heating()                      │
│   ├─ Filter enabled zones                                       │
│   ├─ Categorize: underheated, satisfied, overheated            │
│   │   underheated: [kitchen]                                    │
│   │   satisfied: [bedroom]                                      │
│   │   overheated: []                                            │
│   ├─ Mode: HEATING (underheated zones exist)                   │
│   ├─ Calculate max deficit:                                     │
│   │   kitchen: 24.0 - 22.0 = 2.0°C (maximum)                   │
│   ├─ Formula: main_current + max_deficit                        │
│   └─ Result: 23.0 + 2.0 = 25.0°C                               │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Write Main State to Redis                               │
│   state = {                                                      │
│     "target_temperature": 25.0,                                 │
│     "current_temperature": 23.0,                                │
│     "updated_at": time.time()                                   │
│   }                                                              │
│   await redis_client.set_main_climate_state(state)             │
│   Log: "Main target calculated: 25.0°C"                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Update Main Climate Entity                              │
│   await hass.services.async_call(                               │
│     "climate", "set_temperature",                               │
│     {                                                            │
│       "entity_id": "climate.main_thermostat",                   │
│       "temperature": 25.0                                        │
│     }                                                            │
│   )                                                              │
│   Log: "Main climate updated to 25.0°C"                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ COMPLETE: Coordinator sleeps for 30 seconds                     │
│   Next zones will read updated main_target from Redis           │
└─────────────────────────────────────────────────────────────────┘
```

**NOTE**: Zones do NOT listen to this event. They read the updated `main_target` from Redis whenever they process a temperature change event.

---

### Event 4: Safety Coordinator Timer

**Trigger**: Periodic timer (every 60 seconds)

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: Timer tick (60 seconds elapsed)                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LISTENER: SafetyCoordinator._async_update_data()                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Get All Zones from Redis                                │
│   zones = await redis_client.get_all_zones()                    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Count Open Valves                                       │
│   open_valves = [z for z in zones                              │
│                  if z["valve_state"] in ["open", "opening"]]   │
│   open_count = len(open_valves)                                │
│   min_required = 1                                              │
│   Log: "Safety check: {open_count} valves open (min: {min})"   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Check Minimum Met                                       │
│   If open_count >= min_required:                                │
│     Log: "Safety OK"                                            │
│     Return (nothing to do)                                      │
│   Else:                                                          │
│     Continue to Step 4 (safety violation)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │ (Safety violation)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Find Fallback Zone                                      │
│   fallback_zones = [z for z in zones if z["is_fallback"]]      │
│   If fallback_zones:                                            │
│     fallback = fallback_zones[0]                                │
│   Else:                                                          │
│     fallback = zones[0] (first available)                       │
│   Log: "SAFETY VIOLATION: Only {count} valves open!"           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Force Open Fallback Valve                               │
│   await hass.services.async_call(                               │
│     "multizone_climate", "force_open_valve",                    │
│     {"zone_id": fallback["zone_id"]}                            │
│   )                                                              │
│   Log: "SAFETY: Force opened {zone_id} valve"                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Event 5: User Changes Zone Target Temperature

**Trigger**: User sets new target via UI or service call

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: Service call - climate.set_temperature                   │
│   entity_id: climate.bedroom                                    │
│   temperature: 22.0 (was 21.0)                                  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LISTENER: AutonomousZoneClimate.async_set_temperature()         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Update Target Temperature                               │
│   self._target_temperature = 22.0                               │
│   Log: "Zone bedroom: Target changed to 22.0°C"                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Write to Redis                                          │
│   await self._write_state_to_redis()                            │
│   (Updates target_temperature in Redis)                         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Trigger Re-evaluation                                   │
│   Simulate temperature change event to recalculate               │
│   await self._handle_temperature_change({                        │
│     "data": {                                                    │
│       "new_state": hass.states.get(self.temp_sensor_id),       │
│       "old_state": None                                         │
│     }                                                            │
│   })                                                             │
│   (This runs through full temp change flow)                     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ RESULT: New target may change satisfaction state                │
│   Old: 21.0°C target, 21.0°C current → satisfied               │
│   New: 22.0°C target, 21.0°C current → underheated             │
│   Valve action: OPEN (now needs heat)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

### Event 6: Integration Added to Home Assistant

**Trigger**: Home Assistant loads/reloads the integration

```
┌─────────────────────────────────────────────────────────────────┐
│ EVENT: Integration loaded                                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ LISTENER: AutonomousZoneClimate.async_added_to_hass()           │
│   Called for EACH zone entity                                   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Register Temperature Sensor Listener                    │
│   self.async_on_remove(                                          │
│     async_track_state_change_event(                             │
│       hass, [self.temp_sensor_id],                              │
│       self._handle_temperature_change                           │
│     )                                                            │
│   )                                                              │
│   Log: "Registered listener for {sensor_id}"                   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Initialize Current Temperature                          │
│   temp_state = hass.states.get(self.temp_sensor_id)            │
│   if temp_state:                                                 │
│     self._current_temperature = float(temp_state.state)         │
│   Log: "Initial temperature: {temp}°C"                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Initialize Valve State                                  │
│   valve_state = hass.states.get(self.valve_switch_id)          │
│   if valve_state:                                                │
│     self._valve_state = "open" if valve_state.state == "on"    │
│   Log: "Initial valve state: {state}"                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Write Initial State to Redis                            │
│   await self._write_state_to_redis()                            │
│   Log: "Autonomous zone {zone_id} initialized"                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ COMPLETE: Zone entity ready and listening                       │
│   Waiting for first temperature change event                    │
└─────────────────────────────────────────────────────────────────┘
```

Additionally, coordinators also start:

```
┌─────────────────────────────────────────────────────────────────┐
│ MainClimateCoordinator.async_added_to_hass()                    │
│   └─ Start periodic timer (30s)                                 │
│   └─ Run initial update immediately                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SafetyCoordinator.async_added_to_hass()                         │
│   └─ Start periodic timer (60s)                                 │
│   └─ Run initial update immediately                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Event Interaction Matrix

Shows how different events interact with each other:

| Triggering Event | Affects | How | Latency |
|------------------|---------|-----|---------|
| Zone temp change | Zone valve | Direct: recalc satisfaction → hybrid logic → valve action | < 100ms |
| Zone temp change | Redis zone state | Direct: write updated state | < 50ms |
| Zone temp change | Main target | Indirect: next coordinator cycle reads new zone state | < 30s |
| Main coordinator | Main climate entity | Direct: set new target temp | < 500ms |
| Main coordinator | Redis main state | Direct: write new target | < 50ms |
| Main coordinator | Zone valve decisions | Indirect: zones read main target on next temp change | Variable |
| User target change | Zone satisfaction | Direct: triggers re-evaluation | < 100ms |
| User target change | Zone valve | Direct: via re-evaluation flow | < 200ms |
| Safety coordinator | Fallback valve | Direct: force open if violation | < 500ms |
| Safety coordinator | Other zones | None: independent operation | N/A |

---

## Event Processing Guarantees

### Ordering Guarantees

1. **Zone Temperature Events**: Processed in order received (Home Assistant event queue)
2. **Multiple Zone Events**: No ordering between zones (independent)
3. **Coordinator vs Zone Events**: No coordination (zones autonomous)

### Idempotency

1. **Temperature Change**: Idempotent - same temp → same result
2. **Valve Actions**: Not idempotent - each action counted/logged
3. **Redis Writes**: Idempotent - last write wins

### Error Handling

1. **Event Processing Failure**: Zone logs error, continues listening
2. **Redis Unavailable**: Zone uses cached/fallback values
3. **Valve Action Failure**: Zone logs error, retries next temp change
4. **Coordinator Failure**: Next cycle retries, zones continue autonomously

---

## Performance Characteristics

| Event Type | Frequency | Processing Time | Impact |
|------------|-----------|-----------------|--------|
| Zone temp change | Every temp sensor update (~30-60s) | 50-100ms | Low - single zone |
| Main coordinator | Every 30s | 100-200ms | Low - background |
| Safety coordinator | Every 60s | 50-100ms | Very low |
| User target change | On demand | 100-200ms | Low - single zone |
| Integration reload | Rare (startup/reload) | 1-2s | One-time |

**Total System Load** (3 zones, normal operation):
- Events per minute: ~6 temp changes + 2 coordinator ticks = 8 events
- CPU time per minute: ~1 second total
- Memory: ~50KB per zone + ~5MB baseline

---

## Critical Event Sequences

### Startup Sequence

```
1. Integration loads
2. Zone entities call async_added_to_hass()
3. Event listeners registered
4. Coordinators start
5. Initial states written to Redis
6. Main coordinator calculates first main target
7. System ready - zones listening for temp changes
```

### Shutdown Sequence

```
1. Home Assistant shutdown initiated
2. Zone entities call async_will_remove_from_hass()
3. Event listeners unregistered
4. Coordinators stop
5. Pending tasks cancelled
6. Resources cleaned up
```

### Recovery from Redis Failure

```
1. Redis connection lost
2. Zone temp change event arrives
3. Zone attempts Redis read → fails
4. Zone uses fallback (last known main_target)
5. Zone continues operation with cached values
6. Redis reconnects
7. Next write succeeds, state synchronized
```

---

## Event Debugging

### Logging Event Flow

Enable debug logging to trace events:

```yaml
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug
```

Example log output:
```
[DEBUG] Zone bedroom: Temperature changed 20.9°C → 21.0°C
[DEBUG] Satisfaction calculator: underheated (current < target + epsilon)
[DEBUG] Hybrid controller: open (underheated zone always opens)
[INFO] Zone bedroom: Valve action 'open' executed
[DEBUG] Redis: Zone state written for bedroom
```

### Monitoring Event Performance

Track event processing times:

```python
start = time.time()
await self._handle_temperature_change(event)
duration = (time.time() - start) * 1000
_LOGGER.debug(f"Event processed in {duration:.1f}ms")
```

---

**This document provides complete visibility into all event-driven behavior in the system. Implementation agent should use this as reference for understanding event flows, not as code to copy.**
