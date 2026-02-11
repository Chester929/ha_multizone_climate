# Option 3: Architecture Documentation

## System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Home Assistant Core                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Multizone Climate Integration              │  │
│  │                                                       │  │
│  │  ┌────────────────┐      ┌──────────────────┐       │  │
│  │  │ Climate        │      │  Temperature     │       │  │
│  │  │ Entities       │◄─────│  Sensors         │       │  │
│  │  │ (per zone)     │      │  (existing)      │       │  │
│  │  └────────┬───────┘      └──────────────────┘       │  │
│  │           │                                          │  │
│  │           │ satisfaction state                       │  │
│  │           ▼                                          │  │
│  │  ┌─────────────────────────────────────┐            │  │
│  │  │  Hybrid Valve Controller            │            │  │
│  │  │  ┌──────────────┐  ┌──────────────┐ │            │  │
│  │  │  │  Tier 1:     │  │  Tier 2:     │ │            │  │
│  │  │  │  Temperature │→ │  Deficit     │ │            │  │
│  │  │  │  Safety      │  │  Magnitude   │ │            │  │
│  │  │  └──────────────┘  └──────────────┘ │            │  │
│  │  └────────────┬────────────────────────┘            │  │
│  │               │ valve actions                        │  │
│  │               ▼                                      │  │
│  │  ┌──────────────────────────────┐                   │  │
│  │  │  Valve Manager               │                   │  │
│  │  │  - Safety checks             │                   │  │
│  │  │  - Actuation delays          │                   │  │
│  │  │  - Service call execution    │                   │  │
│  │  └────────────┬─────────────────┘                   │  │
│  │               │                                      │  │
│  └───────────────┼──────────────────────────────────────┘  │
│                  │                                          │
│                  ▼                                          │
│  ┌──────────────────────────────┐                          │
│  │   Valve Switches             │                          │
│  │   (existing entities)        │                          │
│  └──────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                     │
                     │ state persistence
                     ▼
         ┌───────────────────────┐
         │       Redis           │
         │  - Zone states        │
         │  - Main target        │
         │  - Valve locks        │
         │  - Metrics            │
         └───────────────────────┘
```

## Component Architecture

### 1. Hybrid Valve Controller

**Purpose**: Implements two-tier decision logic for satisfied zone valves

**Responsibilities**:
- Evaluate temperature safety (Tier 1)
- Assess deficit magnitude (Tier 2)
- Make valve open/close decisions
- Log decision rationale
- Collect metrics

**Interface**:

```python
class HybridValveController:
    """
    Hybrid valve control with temperature safety and deficit awareness.
    """
    
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
        Returns: 'open' or 'close'
        """
```

**Dependencies**:
- Redis client (for metrics)
- Configuration (for thresholds)
- Logger

**State**: Stateless (all state in Redis)

---

### 2. Valve Controller (Modified)

**Purpose**: Orchestrates valve decisions for all zones

**Changes for Hybrid**:

```python
class ValveController:
    def __init__(self, redis_client, config):
        self.redis_client = redis_client
        self.config = config
        # NEW: Hybrid controller
        self.hybrid_controller = HybridValveController(
            redis_client, 
            config
        )
    
    async def update_valves(
        self,
        zones: list[dict],
        main_climate_state: str,
        multizone_enabled: bool,
    ) -> list[dict]:
        # Existing code for underheated/overheated
        # ...
        
        # NEW: For satisfied zones, use hybrid logic
        if satisfaction == "satisfied":
            # Get current main target
            main_target = await self._get_current_main_target()
            
            # Get underheated zones list
            underheated_zones = [
                z for z in zones 
                if z.get("satisfaction") == "underheated"
            ]
            
            # Hybrid decision
            action = await self.hybrid_controller.determine_valve_action(
                zone_id=zone.get("id"),
                satisfaction=satisfaction,
                zone_target=zone.get("target_temperature"),
                upper_offset=zone.get("closing_offset", 0.3),
                main_target_temp=main_target,
                underheated_zones=underheated_zones,
            )
            
            if action == "open":
                valves_to_open.append(valve_id)
            else:
                valves_to_close.append(valve_id)
```

---

### 3. Zone Climate Entity (No Changes Required)

**Purpose**: Represents individual zone climate control

**Existing Responsibilities**:
- Monitor temperature sensor
- Calculate satisfaction state
- Store target temperature
- Write state to Redis

**Interaction with Hybrid**:
- Provides satisfaction state to valve controller
- No direct interaction with hybrid logic
- Continues to use satisfaction state machine

---

### 4. Main Climate Coordinator (Minimal Changes)

**Purpose**: Calculate main climate target temperature

**Changes**:
```python
class MainClimateCoordinator:
    async def _async_update_data(self):
        # Existing main target calculation
        main_target = self._calculate_main_target_heating(zones)
        
        # NEW: Store with timestamp for staleness detection
        await self.redis_client.set_main_climate_state({
            "target_temperature": main_target,
            "updated_at": time.time(),  # Add timestamp
        })
```

---

### 5. Redis Client (Enhanced)

**Purpose**: State management and persistence

**New Methods**:

```python
class RedisClient:
    async def get_current_main_target(self) -> dict:
        """
        Get main target with staleness information.
        
        Returns:
            {
                "target": float,
                "updated_at": float,
                "is_stale": bool
            }
        """
        main_state = await self.get_main_climate_state()
        updated_at = main_state.get("updated_at", 0)
        
        return {
            "target": main_state.get("target_temperature"),
            "updated_at": updated_at,
            "is_stale": time.time() - updated_at > 60
        }
    
    async def increment_metric(self, key: str):
        """Increment a metric counter."""
        await self.redis.incr(f"metrics:{key}")
    
    async def get_metric(self, key: str) -> int:
        """Get metric value."""
        value = await self.redis.get(f"metrics:{key}")
        return int(value) if value else 0
```

---

## Data Flow Architecture

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Temperature Sensor Event                                 │
│    sensor.bedroom_temp: 21.0°C                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Zone Climate Entity                                      │
│    - Read sensor value: 21.0°C                              │
│    - Compare to target: 21.0°C                              │
│    - Apply state machine (with epsilon)                     │
│    - Result: SATISFIED                                      │
│    - Write to Redis:                                        │
│      multizone:zone:bedroom = {                             │
│        "current_temperature": 21.0,                         │
│        "target_temperature": 21.0,                          │
│        "satisfaction": "satisfied"                          │
│      }                                                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Main Climate Coordinator (periodic, every 30s)          │
│    - Read all zones from Redis                              │
│    - Identify underheated zones:                            │
│      [kitchen: deficit 2.0°C]                               │
│    - Calculate main target:                                 │
│      23.0 + 2.0 = 25.0°C                                    │
│    - Write to Redis:                                        │
│      multizone:main_climate = {                             │
│        "target_temperature": 25.0,                          │
│        "updated_at": 1707563400                             │
│      }                                                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Valve Controller (triggered by temp change)             │
│    - Get all zones from Redis                               │
│    - FOR EACH zone:                                         │
│      IF satisfaction == "underheated":                      │
│        action = "open"                                      │
│      ELIF satisfaction == "overheated":                     │
│        action = "close"                                     │
│      ELIF satisfaction == "satisfied":                      │
│        ┌────────────────────────────────────────────┐      │
│        │ 5. Hybrid Valve Controller                 │      │
│        │    Input:                                   │      │
│        │      - zone_id: "bedroom"                   │      │
│        │      - zone_target: 21.0                    │      │
│        │      - upper_offset: 0.3                    │      │
│        │      - main_target: 25.0                    │      │
│        │      - underheated_zones: [{kitchen: ...}] │      │
│        │                                             │      │
│        │    TIER 1 - Temperature Safety:             │      │
│        │      overheat_threshold = 21.0 + 0.3 = 21.3│      │
│        │      Is 25.0 > 21.3? YES                    │      │
│        │      Decision: CLOSE                        │      │
│        │      (Tier 2 not evaluated)                 │      │
│        │                                             │      │
│        │    Log:                                     │      │
│        │      "TIER 1 - Closing bedroom valve:      │      │
│        │       main_target 25.0°C > threshold 21.3°C"│      │
│        │                                             │      │
│        │    Metrics:                                 │      │
│        │      hybrid_tier1_closures += 1             │      │
│        │                                             │      │
│        │    Return: "close"                          │      │
│        └────────────────────────────────────────────┘      │
│        action = "close"                                     │
│                                                             │
│    - Collect actions:                                       │
│      kitchen: open                                          │
│      bedroom: close                                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Valve Manager                                            │
│    - Apply safety checks (min valves open)                  │
│    - Check valve locks (actuation delay)                    │
│    - Execute service calls:                                 │
│      await hass.services.async_call(                        │
│        "switch", "turn_on",                                 │
│        {"entity_id": "switch.kitchen_valve"}                │
│      )                                                       │
│      await hass.services.async_call(                        │
│        "switch", "turn_off",                                │
│        {"entity_id": "switch.bedroom_valve"}                │
│      )                                                       │
│    - Set valve locks (120s timeout)                         │
│    - Update valve states in Redis                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagrams

### Tier 1 Decision (Temperature Safety)

```
Zone Entity    Valve Controller    Hybrid Controller    Redis
     │                 │                    │              │
     │ temp_changed    │                    │              │
     ├────────────────>│                    │              │
     │                 │ get_main_target    │              │
     │                 ├───────────────────────────────────>│
     │                 │<───────────────────────────────────┤
     │                 │ main_target: 25°C  │              │
     │                 │                    │              │
     │                 │ determine_action   │              │
     │                 ├───────────────────>│              │
     │                 │ (zone_target: 21°C,│              │
     │                 │  main_target: 25°C)│              │
     │                 │                    │              │
     │                 │                    │ TIER 1:      │
     │                 │                    │ 25 > 21.3?   │
     │                 │                    │ YES → CLOSE  │
     │                 │                    │              │
     │                 │                    │ log_decision │
     │                 │                    ├─────────────>│
     │                 │                    │              │
     │                 │                    │ incr_metric  │
     │                 │                    ├─────────────>│
     │                 │                    │              │
     │                 │ action: "close"    │              │
     │                 │<───────────────────┤              │
     │                 │                    │              │
     │                 │ execute_close      │              │
     │                 ├───────────────────────────────────>│
     │                 │                    │              │
```

### Tier 2 Decision (Deficit Magnitude)

```
Zone Entity    Valve Controller    Hybrid Controller    Redis
     │                 │                    │              │
     │ temp_changed    │                    │              │
     ├────────────────>│                    │              │
     │                 │ get_main_target    │              │
     │                 ├───────────────────────────────────>│
     │                 │<───────────────────────────────────┤
     │                 │ main_target: 24°C  │              │
     │                 │                    │              │
     │                 │ determine_action   │              │
     │                 ├───────────────────>│              │
     │                 │ (zone_target: 24°C,│              │
     │                 │  main_target: 24°C,│              │
     │                 │  underheated: [    │              │
     │                 │    {deficit: 2.0}  │              │
     │                 │  ])                │              │
     │                 │                    │              │
     │                 │                    │ TIER 1:      │
     │                 │                    │ 24 > 24.3?   │
     │                 │                    │ NO → Continue│
     │                 │                    │              │
     │                 │                    │ TIER 2:      │
     │                 │                    │ max_deficit  │
     │                 │                    │ = 2.0        │
     │                 │                    │ 2.0 > 1.0?   │
     │                 │                    │ YES → CLOSE  │
     │                 │                    │              │
     │                 │                    │ log_decision │
     │                 │                    ├─────────────>│
     │                 │                    │              │
     │                 │                    │ incr_metric  │
     │                 │                    ├─────────────>│
     │                 │                    │              │
     │                 │ action: "close"    │              │
     │                 │<───────────────────┤              │
     │                 │                    │              │
     │                 │ execute_close      │              │
     │                 ├───────────────────────────────────>│
     │                 │                    │              │
```

---

## Database Schema (Redis)

### Zone State

**Key**: `multizone:zone:{zone_id}`
**Type**: Hash

```
{
  "id": "bedroom",
  "name": "Bedroom",
  "enabled": "true",
  "current_temperature": 21.0,
  "target_temperature": 21.0,
  "satisfaction": "satisfied",
  "valve_state": "open",
  "valve_id": "switch.bedroom_valve",
  "closing_offset": 0.3,
  "opening_offset": 0.3,
  "deficit_threshold": 1.0,  // NEW
  "priority": 50,
  "is_fallback": false,
  "updated_at": 1707563400
}
```

### Main Climate State

**Key**: `multizone:main_climate`
**Type**: Hash

```
{
  "target_temperature": 25.0,
  "current_temperature": 23.0,
  "updated_at": 1707563400,  // NEW for staleness check
  "state": "heat"
}
```

### Metrics

**Keys**: `metrics:{metric_name}`
**Type**: String (integer counter)

```
metrics:hybrid_tier1_closures = "42"
metrics:hybrid_tier2_closures = "18"
metrics:hybrid_open_decisions = "230"
metrics:hybrid_total_decisions = "290"
```

### Valve Locks

**Key**: `multizone:valve:lock:{zone_id}`
**Type**: String with TTL

```
multizone:valve:lock:bedroom = "valve_close"
TTL: 120 seconds
```

---

## Configuration Architecture

### Configuration Layers

```
┌──────────────────────────────────────────────────┐
│ Layer 1: System Defaults (in code)              │
│   DEFAULT_DEFICIT_THRESHOLD = 1.0               │
│   DEFAULT_UPPER_OFFSET = 0.3                    │
│   DEFAULT_VALVE_DELAY = 120                     │
└────────────────┬─────────────────────────────────┘
                 │ Override
                 ▼
┌──────────────────────────────────────────────────┐
│ Layer 2: Global Config (integration config)     │
│   multizone_climate:                            │
│     deficit_threshold: 1.2                      │
│     min_valves_open: 1                          │
└────────────────┬─────────────────────────────────┘
                 │ Override
                 ▼
┌──────────────────────────────────────────────────┐
│ Layer 3: Zone-Specific Config (per zone)        │
│   zones:                                        │
│     bedroom:                                    │
│       deficit_threshold: 0.8                    │
└──────────────────────────────────────────────────┘
```

### Configuration Resolution

```python
def get_deficit_threshold(zone_id: str, config: dict) -> float:
    """Get deficit threshold with proper precedence."""
    
    # Layer 3: Zone-specific
    zone_threshold = config.get(f"zone_{zone_id}_deficit_threshold")
    if zone_threshold is not None:
        return zone_threshold
    
    # Layer 2: Global config
    global_threshold = config.get("deficit_threshold")
    if global_threshold is not None:
        return global_threshold
    
    # Layer 1: System default
    return HybridValveController.DEFAULT_DEFICIT_THRESHOLD
```

---

## Integration Points

### 1. Home Assistant Event System

**Subscribed Events**:
- `state_changed` for temperature sensors
- `state_changed` for valve switches

**Published Events**:
- None (uses service calls instead)

### 2. Home Assistant Services

**Called Services**:
- `switch.turn_on` (open valve)
- `switch.turn_off` (close valve)

**Provided Services**:
- None (uses built-in climate services)

### 3. Redis Pub/Sub (Optional)

**Published Channels**:
```python
# Notify when hybrid decision made
await redis.publish(
    "multizone:hybrid_decision",
    json.dumps({
        "zone_id": "bedroom",
        "action": "close",
        "tier": 1,
        "reason": "temperature_safety"
    })
)
```

**Subscribed Channels**:
- None currently (future: external control)

---

## Error Handling Architecture

### Error Propagation

```
┌──────────────────────────────────────┐
│ Hybrid Controller                    │
│   try:                               │
│     main_target = get_main_target()  │
│   except RedisError:                 │
│     use_fallback_value()             │
│     log_error()                      │
│     continue_operation()             │
└──────────────────────────────────────┘
        │ Errors logged, operation continues
        ▼
┌──────────────────────────────────────┐
│ Valve Controller                     │
│   try:                               │
│     action = hybrid.determine()      │
│   except Exception:                  │
│     default_safe_action()            │
│     log_error()                      │
│     alert_user()                     │
└──────────────────────────────────────┘
```

### Failure Modes

| Component | Failure | Behavior | Recovery |
|-----------|---------|----------|----------|
| Redis connection | Lost | Use cached values | Auto-reconnect |
| Main target stale | > 60s old | Trigger recalc | Wait 0.5s |
| Temperature sensor | Invalid | Use last valid | Alert user |
| Valve switch | Unresponsive | Log error, retry | Manual intervention |
| Hybrid logic | Exception | Default to OPEN | Log for analysis |

---

## Performance Architecture

### Caching Strategy

```python
class HybridValveController:
    def __init__(self, redis_client, config):
        self.redis_client = redis_client
        self.config = config
        
        # Cache for performance
        self._main_target_cache = {
            "value": None,
            "timestamp": 0,
            "ttl": 5  # Cache for 5 seconds
        }
    
    async def _get_main_target_cached(self) -> float:
        """Get main target with short-term caching."""
        now = time.time()
        
        if (self._main_target_cache["value"] is not None and
            now - self._main_target_cache["timestamp"] < self._main_target_cache["ttl"]):
            return self._main_target_cache["value"]
        
        # Cache miss - fetch from Redis
        main_target = await self.redis_client.get_current_main_target()
        self._main_target_cache["value"] = main_target
        self._main_target_cache["timestamp"] = now
        
        return main_target
```

### Batch Operations

```python
async def update_all_zones(self, zones):
    """Update all zones efficiently with batch Redis operations."""
    
    # Batch read all zone states
    zone_states = await self.redis_client.mget([
        f"multizone:zone:{z['id']}" for z in zones
    ])
    
    # Process decisions
    actions = []
    for zone, state in zip(zones, zone_states):
        action = await self.determine_valve_action(...)
        actions.append(action)
    
    # Batch write metrics
    await self.redis_client.pipeline([
        ("incr", f"metrics:{metric}") 
        for metric in collected_metrics
    ])
    
    return actions
```

---

## Monitoring Architecture

### Metrics Collection

```python
class HybridMetrics:
    """Collect and expose hybrid controller metrics."""
    
    async def record_decision(
        self, 
        zone_id: str,
        tier: int,
        action: str,
        decision_time_ms: float
    ):
        """Record a hybrid decision."""
        await asyncio.gather(
            self.redis.incr(f"metrics:hybrid_tier{tier}_{action}s"),
            self.redis.lpush(
                "metrics:decision_times",
                decision_time_ms,
                maxlen=1000  # Keep last 1000
            ),
            self.redis.hincrby(
                f"metrics:zone_{zone_id}",
                f"tier{tier}_{action}s",
                1
            )
        )
```

### Health Checks

```python
async def health_check(self) -> dict:
    """Check system health."""
    return {
        "hybrid_controller": {
            "status": "healthy",
            "total_decisions_24h": await self.get_decisions_count(24),
            "tier1_percentage": await self.get_tier_percentage(1),
            "tier2_percentage": await self.get_tier_percentage(2),
            "avg_decision_time_ms": await self.get_avg_decision_time(),
        },
        "redis": {
            "status": "connected" if await self.redis.ping() else "disconnected",
            "latency_ms": await self.measure_redis_latency(),
        }
    }
```

---

## Deployment Architecture

### Container Structure (if using addon)

```
┌────────────────────────────────────────────┐
│ Multizone Climate Add-on                   │
├────────────────────────────────────────────┤
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │ Redis Container                      │ │
│  │   - Persistence: AOF                 │ │
│  │   - Memory: 256MB                    │ │
│  │   - Port: 6379 (internal)           │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │ Home Assistant Container             │ │
│  │   - Custom Component                 │ │
│  │     - Hybrid Controller ⭐           │ │
│  │     - Valve Controller               │ │
│  │     - Zone Entities                  │ │
│  └──────────────────────────────────────┘ │
│                                            │
└────────────────────────────────────────────┘
```

### File Structure

```
multizone_climate/
├── custom_components/
│   └── multizone_climate/
│       ├── __init__.py
│       ├── climate.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       └── core/
│           ├── __init__.py
│           ├── algorithms.py
│           ├── hybrid_valve_controller.py  ⭐ NEW
│           ├── metrics.py  ⭐ NEW
│           ├── redis_client.py  (enhanced)
│           ├── satisfaction.py
│           └── valve_control.py  (modified)
```

---

**Status: ARCHITECTURE DOCUMENTED**

Complete architecture documentation for Option 3 Hybrid Valve Control including components, data flow, database schema, configuration, integration points, error handling, performance, monitoring, and deployment.
