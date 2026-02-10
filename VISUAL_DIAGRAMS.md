# Visual Diagrams: Current vs Proposed Behavior

## Scenario A: Main Climate Target Manual Change

### Current Behavior (❌ BROKEN)

```
┌─────────────────────────────────────────────────────────────────┐
│ Timeline: User Manually Sets Main Climate Target                │
└─────────────────────────────────────────────────────────────────┘

T=0s     User Action: Set main climate to 28°C via UI
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 28°C         │  ← User sees their change
         └──────────────────────┘

T=5s     System continues...
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 28°C         │  ← Still shows 28°C
         └──────────────────────┘
         
         User thinks: ✅ "Good, system accepted my 28°C"

T=30s    Main Coordinator runs periodic update
         ┌──────────────────────┐
         │ Coordinator:         │
         │ Calculate target     │
         │ based on zones       │
         │ Result: 23°C         │  ← Overwrites user's 28°C!
         └──────────────────────┘
         
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 23°C         │  ← User's change GONE!
         └──────────────────────┘
         
         User thinks: ❌ "WTF? My 28°C disappeared!"

T=31s    User is confused and frustrated
         No notification, no explanation, no indication
         Manual control is IMPOSSIBLE

Problems:
❌ User's manual change silently overwritten
❌ No feedback or notification
❌ Emergency override impossible
❌ Poor user experience
❌ System appears broken
```

---

### Proposed Behavior: Solution A2 (✅ FIXED)

```
┌─────────────────────────────────────────────────────────────────┐
│ Timeline: User Manually Sets Main Climate Target                │
│ WITH TEMPORARY OVERRIDE MODE                                     │
└─────────────────────────────────────────────────────────────────┘

T=0s     User Action: Set main climate to 28°C via UI
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 28°C         │  ← User sets target
         └──────────────────────┘

T=0.1s   Event Listener detects change (NOT from coordinator)
         ┌──────────────────────────────────────────┐
         │ MainClimateCoordinator                   │
         │ Detected: Manual change to 28°C         │
         │ Action: ENTER OVERRIDE MODE              │
         │ Duration: 60 minutes                     │
         │ Pause automatic calculations             │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────────────────────────┐
         │ climate.main                             │
         │ Target: 28°C                             │
         │ override_active: true                    │
         │ override_expires_at: 13:52 (in 60 min) │
         │ override_by: manual_user                 │
         └──────────────────────────────────────────┘
         
         📱 Notification sent:
         "Manual override active. System will resume 
          automatic control in 60 minutes."

T=5s     System respects override
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 28°C         │  ← Still 28°C ✓
         │ override_active: ✅  │
         └──────────────────────┘

T=30s    Coordinator runs but SKIPS update (override mode)
         ┌──────────────────────────────────────────┐
         │ Coordinator:                             │
         │ Check: Override active? YES              │
         │ Action: SKIP target calculation          │
         │ Log: "Skipping update (manual override)" │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 28°C         │  ← Still 28°C! ✓
         │ override_active: ✅  │
         │ (expires in 59:30)   │
         └──────────────────────┘
         
         User thinks: ✅ "Perfect! My 28°C is respected!"

T=60min  Override expires, automatic control resumes
         ┌──────────────────────────────────────────┐
         │ Coordinator:                             │
         │ Override expired, resume calculations    │
         │ Calculate target: 23°C                   │
         │ Update main climate                      │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────┐
         │ climate.main         │
         │ Target: 23°C         │  ← Back to automatic
         │ override_active: ❌  │
         └──────────────────────┘
         
         📱 Notification sent:
         "Manual override expired. Automatic 
          control resumed. Target: 23°C"

Benefits:
✅ User's manual change respected
✅ Clear indication of override state
✅ Automatic return to automation
✅ User informed via notifications
✅ Emergency override possible
✅ Good user experience
```

---

## Scenario B: External Valve Closure

### Current Behavior (❌ BROKEN)

```
┌─────────────────────────────────────────────────────────────────┐
│ Timeline: User Manually Closes Bedroom Valve                    │
└─────────────────────────────────────────────────────────────────┘

T=0s     User Action: Turn off bedroom valve via UI
         (Maybe room too hot, window open, maintenance, etc.)
         
         ┌──────────────────────┐
         │ switch.bedroom_valve │
         │ State: OFF           │  ← Valve physically closes
         └──────────────────────┘

T=0.1s   Nothing happens! No event listener!
         ┌──────────────────────────────────────────┐
         │ AutonomousZoneClimate (Bedroom)          │
         │ Last known state: valve OPEN             │
         │ No event received!                       │
         │ Still thinks valve is OPEN               │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────────────────────────┐
         │ Redis:                                   │
         │ bedroom.valve_state: "open"              │
         │ ← WRONG! Out of sync with reality!      │
         └──────────────────────────────────────────┘

T=0s-5min  STATE INCONSISTENCY WINDOW
         ┌────────────────────────────────────────┐
         │ Reality:                               │
         │   Valve is CLOSED (user turned off)    │
         │                                        │
         │ Zone Entity State:                     │
         │   Valve is OPEN (last known)           │
         │                                        │
         │ Redis State:                           │
         │   Valve is OPEN (wrong!)               │
         │                                        │
         │ Duration: Until next temp change event │
         │ ⚠️ Could be MINUTES! ⚠️               │
         └────────────────────────────────────────┘

T=5min   Temperature event finally triggers
         ┌──────────────────────────────────────────┐
         │ sensor.bedroom_temperature changes       │
         │ ↓                                        │
         │ Zone processes event                     │
         │ ↓                                        │
         │ Decides valve should be OPEN (underheated)│
         │ ↓                                        │
         │ Queries current valve state              │
         │ Found: switch is OFF!                    │
         │ ↓                                        │
         │ Updates internal state to "closed"       │
         │ ↓                                        │
         │ Decides to OPEN valve                    │
         │ ↓                                        │
         │ Executes: switch.turn_on()              │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────┐
         │ switch.bedroom_valve │
         │ State: ON            │  ← SYSTEM FIGHTS USER!
         └──────────────────────┘
         
         User thinks: ❌ "WTF? I closed it! Why did it reopen?"

T=5min+  Valve cycling battle begins
         User closes → System opens → User closes → System opens...

Problems:
❌ State inconsistency (could be minutes!)
❌ System fights user intent
❌ No manual control possible
❌ Safety violation risk (if multiple valves closed)
❌ Poor user experience
❌ Energy waste (heating room with open window)
```

---

### Proposed Behavior: Solution B1 (✅ FIXED)

```
┌─────────────────────────────────────────────────────────────────┐
│ Timeline: User Manually Closes Bedroom Valve                    │
│ WITH STATE CHANGE LISTENER                                      │
└─────────────────────────────────────────────────────────────────┘

T=0s     User Action: Turn off bedroom valve via UI
         ┌──────────────────────┐
         │ switch.bedroom_valve │
         │ State: OFF           │  ← Valve physically closes
         └──────────────────────┘

T=0.1s   Event Listener detects change IMMEDIATELY
         ┌──────────────────────────────────────────┐
         │ AutonomousZoneClimate (Bedroom)          │
         │ Event: switch.bedroom_valve state_changed│
         │ Old: ON, New: OFF                        │
         │ ↓                                        │
         │ Check: Was this change initiated by us?  │
         │ Last command timestamp: 10 min ago       │
         │ Answer: NO - this is EXTERNAL change     │
         │ ↓                                        │
         │ Update internal state: valve = "closed"  │
         │ Write to Redis: valve_state = "closed"   │
         │ ↓                                        │
         │ Check zone config: manual_valve_override?│
         │ Config: manual_valve_override: true      │
         │ ↓                                        │
         │ Decision: RESPECT external closure       │
         │ ↓                                        │
         │ Log: "External valve closure detected,   │
         │       respecting manual control"         │
         └──────────────────────────────────────────┘
         
         ┌──────────────────────────────────────────┐
         │ Redis:                                   │
         │ bedroom.valve_state: "closed"            │
         │ bedroom.manual_override: true            │
         │ bedroom.override_at: timestamp           │
         │ ← CORRECT! In sync! ✓                   │
         └──────────────────────────────────────────┘
         
         NO STATE INCONSISTENCY! ✅

T=1s     Zone re-evaluates
         ┌──────────────────────────────────────────┐
         │ AutonomousZoneClimate (Bedroom)          │
         │ Current state:                           │
         │   - Temperature: 21°C (satisfied)        │
         │   - Valve: closed (manual override)      │
         │   - Manual override active: YES          │
         │ ↓                                        │
         │ Decision: Keep valve CLOSED              │
         │ Reason: Manual override respected        │
         │ ↓                                        │
         │ Update main coordinator:                 │
         │   Exclude bedroom from calculations      │
         │   (user wants manual control)            │
         └──────────────────────────────────────────┘

T=5min   Temperature changes, zone rechecks
         ┌──────────────────────────────────────────┐
         │ sensor.bedroom_temperature: 20.5°C       │
         │ ↓                                        │
         │ Zone calculates: now UNDERHEATED         │
         │ Normal logic: Would open valve           │
         │ BUT: manual_override: true               │
         │ ↓                                        │
         │ Decision: Keep valve CLOSED              │
         │ Reason: Respecting manual override       │
         │ ↓                                        │
         │ Log: "Zone underheated but manual        │
         │       override active, valve stays closed"│
         └──────────────────────────────────────────┘
         
         ┌──────────────────────┐
         │ switch.bedroom_valve │
         │ State: OFF           │  ← Stays closed! ✓
         └──────────────────────┘
         
         User thinks: ✅ "Perfect! System respects my choice!"

Optional: User can clear override by manually opening valve
         ┌──────────────────────────────────────────┐
         │ User: Turn ON bedroom valve              │
         │ ↓                                        │
         │ Zone detects: External change to ON      │
         │ ↓                                        │
         │ Action: Clear manual override flag       │
         │ Resume automatic control                 │
         │ ↓                                        │
         │ Log: "Manual override cleared,           │
         │       resuming automatic control"        │
         └──────────────────────────────────────────┘

Benefits:
✅ Immediate detection (no delay!)
✅ No state inconsistency
✅ Respects user intent
✅ Manual control possible
✅ Safety violations detected quickly
✅ Good user experience
✅ Energy savings (respects open window scenario)
```

---

## Comparison Summary

### Scenario A: Main Climate Target

| Aspect | Current (Broken) | Solution A2 (Fixed) |
|--------|------------------|---------------------|
| Manual change detection | ❌ No | ✅ Immediate |
| User change respected | ❌ No (overwritten in 30s) | ✅ Yes (60 min) |
| User feedback | ❌ None | ✅ Notifications + attributes |
| Emergency override | ❌ Impossible | ✅ Possible |
| State clarity | ❌ Confusing | ✅ Clear indicators |
| Automatic recovery | ❌ N/A | ✅ After timeout |

### Scenario B: External Valve Closure

| Aspect | Current (Broken) | Solution B1 (Fixed) |
|--------|------------------|---------------------|
| External change detection | ❌ Delayed (minutes) | ✅ Immediate (<1s) |
| State consistency | ❌ Inconsistent | ✅ Always consistent |
| User intent respected | ❌ No (system fights) | ✅ Yes (configurable) |
| Safety violations | ❌ Not detected quickly | ✅ Detected immediately |
| Manual control | ❌ Impossible | ✅ Possible |
| Energy efficiency | ❌ Wastes energy | ✅ Respects user actions |

---

## Security & Safety Impact

### Current System Risks

**Scenario: Multiple Valves Closed Externally**
```
T=0s     User closes Bedroom valve (maintenance)
         System: Doesn't notice ❌
         
T=1min   Automation closes Kitchen valve (some condition)
         System: Doesn't notice ❌
         
T=2min   User closes Living Room valve (window open)
         System: Doesn't notice ❌
         
T=3min   ALL VALVES CLOSED!
         Main climate: Still running, pumping hot water
         No valve open: PRESSURE BUILDS UP
         Safety violation: CRITICAL! ⚠️⚠️⚠️
         
T=63min  Safety Coordinator runs periodic check (60s interval)
         Finally detects: "Only 0 valves open!"
         Force opens fallback valve
         
         But: 60 SECONDS OF DANGER! ⚠️
```

### With Solution B1 (Fixed)

```
T=0s     User closes Bedroom valve
         System: Detects immediately ✅
         Updates state, checks safety
         
T=1min   Automation closes Kitchen valve
         System: Detects immediately ✅
         Updates state, checks safety
         Count: 1 valve remaining (Living Room)
         Status: OK (above minimum)
         
T=2min   User closes Living Room valve
         System: Detects immediately ✅
         Updates state, checks safety
         Count: 0 valves remaining
         Status: VIOLATION! ⚠️
         ↓
         Action: Force open fallback valve
         Response time: < 1 second ✅
         
         SAFETY MAINTAINED! ✅
```

---

**Conclusion**: Solutions A2 + B1 transform the system from broken/unsafe to reliable/safe.
