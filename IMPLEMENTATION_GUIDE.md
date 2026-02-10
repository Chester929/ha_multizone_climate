# Implementation Guide - Fully Autonomous Zones with Hybrid Valve Control

## ⚠️ **CODE EXAMPLES NOTICE**

**All code examples in this guide are for ILLUSTRATION ONLY.**

Implementation agents must:
- ✅ Understand the logic and intent from examples
- ✅ Write production-quality code following Python/HA standards
- ✅ Implement proper error handling, type hints, and documentation
- ✅ Apply Home Assistant best practices
- ❌ Do NOT copy-paste code from this document
- ❌ Do NOT use examples as production code

Examples show **what to do**, production code shows **how to do it properly**.

---

## Overview

This guide provides step-by-step instructions for implementing the Fully Autonomous Zones with Hybrid Valve Control system from scratch.

**Target Audience**: Implementation agent or developer

**Prerequisites**:
- Home Assistant development environment
- Python 3.11+
- Redis server (will be bundled in addon)
- Understanding of Home Assistant custom components

---

## Implementation Order

The implementation should follow this order to minimize dependencies and enable incremental testing:

```
1. Core Logic Components (Pure Python, No Dependencies)
   └─> 2. Redis Client (State Storage)
       └─> 3. Valve Manager (Service Calls)
           └─> 4. Zone Climate Entity (Integration)
               └─> 5. Coordinators (Periodic Tasks)
                   └─> 6. Config Flow (User Setup)
                       └─> 7. Addon (Redis Container)
```

---

## Phase 1: Core Logic Components

### Task 1.1: Create Satisfaction Calculator

**File**: `custom_components/multizone_climate/core/satisfaction.py`

**Purpose**: Pure logic for calculating zone satisfaction state with hysteresis

**Implementation**:

```python
"""Satisfaction state calculation with hysteresis."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


class SatisfactionCalculator:
    """
    Calculate zone satisfaction state with hysteresis to prevent oscillation.
    
    States:
    - underheated: current < (target - lower_offset)
    - satisfied: within acceptable range with hysteresis
    - overheated: current > (target + upper_offset)
    
    Hysteresis prevents rapid state transitions:
    - Once underheated → must reach (target + epsilon) to become satisfied
    - Once overheated → must reach (target - epsilon) to become satisfied
    """
    
    def __init__(
        self,
        lower_offset: float = 0.0,
        upper_offset: float = 0.3,
        satisfaction_epsilon: float = 0.1,
    ):
        """Initialize satisfaction calculator.
        
        Args:
            lower_offset: Temp below target to trigger underheated
            upper_offset: Temp above target to trigger overheated
            satisfaction_epsilon: Hysteresis buffer to prevent oscillation
        
        Raises:
            ValueError: If epsilon is too large relative to offsets
        """
        self.lower_offset = lower_offset
        self.upper_offset = upper_offset
        self.satisfaction_epsilon = satisfaction_epsilon
        
        # Validation: epsilon must be smaller than offsets
        min_offset = min(lower_offset, upper_offset) if lower_offset > 0 else upper_offset
        if satisfaction_epsilon >= min_offset - 0.1:
            raise ValueError(
                f"satisfaction_epsilon ({satisfaction_epsilon}) must be at least "
                f"0.1 less than minimum offset ({min_offset})"
            )
    
    def calculate(
        self,
        current_temp: float,
        target_temp: float,
        previous_satisfaction: str = "unknown",
    ) -> str:
        """
        Calculate satisfaction state with hysteresis.
        
        Args:
            current_temp: Current zone temperature
            target_temp: Target zone temperature
            previous_satisfaction: Previous satisfaction state for hysteresis
        
        Returns:
            "underheated", "satisfied", or "overheated"
        """
        
        # Calculate threshold temperatures
        underheated_threshold = target_temp - self.lower_offset
        overheated_threshold = target_temp + self.upper_offset
        
        # Direct transitions (clear threshold breaches)
        if current_temp < underheated_threshold:
            if previous_satisfaction != "underheated":
                _LOGGER.debug(
                    f"State change → UNDERHEATED: {current_temp:.1f}°C < {underheated_threshold:.1f}°C"
                )
            return "underheated"
        
        if current_temp > overheated_threshold:
            if previous_satisfaction != "overheated":
                _LOGGER.debug(
                    f"State change → OVERHEATED: {current_temp:.1f}°C > {overheated_threshold:.1f}°C"
                )
            return "overheated"
        
        # Hysteresis zone - state depends on previous state
        if previous_satisfaction == "underheated":
            # Must warm up to (target + epsilon) to become satisfied
            satisfied_threshold = target_temp + self.satisfaction_epsilon
            if current_temp >= satisfied_threshold:
                _LOGGER.debug(
                    f"State change → SATISFIED: {current_temp:.1f}°C >= {satisfied_threshold:.1f}°C"
                )
                return "satisfied"
            # Stay underheated
            return "underheated"
        
        elif previous_satisfaction == "overheated":
            # Must cool down to (target - epsilon) to become satisfied
            satisfied_threshold = target_temp - self.satisfaction_epsilon
            if current_temp <= satisfied_threshold:
                _LOGGER.debug(
                    f"State change → SATISFIED: {current_temp:.1f}°C <= {satisfied_threshold:.1f}°C"
                )
                return "satisfied"
            # Stay overheated
            return "overheated"
        
        # Already satisfied or unknown state - stay satisfied if in acceptable range
        return "satisfied"
```

**Test**: Create `tests/test_satisfaction.py`

```python
"""Tests for satisfaction calculator."""
import pytest
from custom_components.multizone_climate.core.satisfaction import SatisfactionCalculator


def test_underheated_state():
    """Test underheated state detection."""
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    
    # Below target
    assert calc.calculate(20.0, 21.0, "unknown") == "underheated"
    assert calc.calculate(20.5, 21.0, "unknown") == "underheated"


def test_overheated_state():
    """Test overheated state detection."""
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    
    # Above target + offset
    assert calc.calculate(21.4, 21.0, "unknown") == "overheated"
    assert calc.calculate(22.0, 21.0, "unknown") == "overheated"


def test_satisfied_state():
    """Test satisfied state."""
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    
    # In acceptable range
    assert calc.calculate(21.0, 21.0, "unknown") == "satisfied"
    assert calc.calculate(21.2, 21.0, "satisfied") == "satisfied"


def test_hysteresis_underheated_to_satisfied():
    """Test hysteresis when transitioning from underheated."""
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    
    # Was underheated, now at target - should still be underheated
    assert calc.calculate(21.0, 21.0, "underheated") == "underheated"
    
    # Must reach target + epsilon to become satisfied
    assert calc.calculate(21.1, 21.0, "underheated") == "satisfied"


def test_hysteresis_overheated_to_satisfied():
    """Test hysteresis when transitioning from overheated."""
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    
    # Was overheated, now at target - should still be overheated
    assert calc.calculate(21.0, 21.0, "overheated") == "overheated"
    
    # Must reach target - epsilon to become satisfied
    assert calc.calculate(20.9, 21.0, "overheated") == "satisfied"


def test_invalid_epsilon():
    """Test that invalid epsilon raises error."""
    with pytest.raises(ValueError):
        SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.3)
```

---

### Task 1.2: Create Hybrid Valve Controller

**File**: `custom_components/multizone_climate/core/hybrid_valve.py`

**Purpose**: Two-tier decision logic for valve control

**Implementation**: (See COMPLETE_SOLUTION_DESIGN.md, HybridValveController class)

**Test**: Create `tests/test_hybrid_valve.py`

```python
"""Tests for hybrid valve controller."""
import pytest
from custom_components.multizone_climate.core.hybrid_valve import HybridValveController


def test_underheated_always_open():
    """Test that underheated zones always get valve opened."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="underheated",
        zone_target=21.0,
        upper_offset=0.3,
        main_target_temp=25.0,
        underheated_zones=[],
    )
    
    assert result == "open"


def test_overheated_always_close():
    """Test that overheated zones always get valve closed."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="overheated",
        zone_target=21.0,
        upper_offset=0.3,
        main_target_temp=23.0,
        underheated_zones=[],
    )
    
    assert result == "close"


def test_satisfied_no_competition():
    """Test satisfied zone stays open when no underheated zones."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=21.0,
        upper_offset=0.3,
        main_target_temp=23.0,
        underheated_zones=[],  # No competition
    )
    
    assert result == "open"


def test_tier1_temperature_safety():
    """Test Tier 1: Close when main target would overheat."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=21.0,
        upper_offset=0.3,
        main_target_temp=25.0,  # 25 > 21.3 (would overheat)
        underheated_zones=[{"zone_id": "kitchen", "deficit": 0.5}],
    )
    
    assert result == "close"  # Tier 1 fails


def test_tier2_deficit_magnitude():
    """Test Tier 2: Close when large deficit exists."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=24.0,
        upper_offset=0.3,
        main_target_temp=24.0,  # Safe temp (24 < 24.3)
        underheated_zones=[{"zone_id": "kitchen", "deficit": 2.0}],  # Large deficit
    )
    
    assert result == "close"  # Tier 2 fails


def test_both_checks_pass():
    """Test when both tiers pass - valve stays open."""
    controller = HybridValveController(deficit_threshold=1.0)
    
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=24.0,
        upper_offset=0.3,
        main_target_temp=24.0,  # Safe temp
        underheated_zones=[{"zone_id": "kitchen", "deficit": 0.5}],  # Small deficit
    )
    
    assert result == "open"  # Both checks pass
```

---

## Phase 2: Redis Client

### Task 2.1: Create Redis Client

**File**: `custom_components/multizone_climate/core/redis_client.py`

**Purpose**: Interface to Redis for state storage

**Key Methods**:
- `get_zone_state(zone_id)` - Get zone state
- `set_zone_state(zone_id, state)` - Write zone state
- `get_all_zones()` - Get all zones
- `get_main_climate_state()` - Get main climate state
- `set_main_climate_state(state)` - Write main climate state
- `get_config(key, default)` - Get configuration value

**Implementation**: Standard Redis hash operations with error handling

---

## Phase 3: Valve Manager

### Task 3.1: Create Valve Manager

**File**: `custom_components/multizone_climate/core/valve_manager.py`

**Purpose**: Execute valve actions with delays and locks

**Key Features**:
- Valve actuation delay enforcement
- Service call execution
- Error handling and retry logic

---

## Phase 4: Zone Climate Entity

### Task 4.1: Create Autonomous Zone Climate Entity

**File**: `custom_components/multizone_climate/climate.py`

**Purpose**: Main zone entity with event-driven logic

**Implementation**: See COMPLETE_SOLUTION_DESIGN.md, AutonomousZoneClimate class

**Key Points**:
- Register event listener in `async_added_to_hass()`
- Handle temperature changes in `_handle_temperature_change()`
- Use hybrid controller for valve decisions
- Write state to Redis on every change

---

## Phase 5: Coordinators

### Task 5.1: Create Main Climate Coordinator

**File**: `custom_components/multizone_climate/coordinator.py`

**Purpose**: Periodic main climate target calculation

**Implementation**: See COMPLETE_SOLUTION_DESIGN.md, MainClimateCoordinator class

---

### Task 5.2: Create Safety Coordinator

**File**: `custom_components/multizone_climate/coordinator.py` (same file)

**Purpose**: Ensure minimum valves open

**Implementation**: See COMPLETE_SOLUTION_DESIGN.md, SafetyCoordinator class

---

## Phase 6: Config Flow

### Task 6.1: Create Config Flow

**File**: `custom_components/multizone_climate/config_flow.py`

**Steps**:
1. Select main climate entity
2. Add zones (repeatable)
3. Global settings

**Validation**:
- Entity IDs exist
- Temperature ranges valid
- Epsilon constraints met

---

## Phase 7: Addon

### Task 7.1: Create Redis Addon

**File**: `addon/config.yaml`

**Purpose**: Simple Redis container + component installer

**Features**:
- Bundled Redis
- Auto-install custom component
- Restart notification

---

## Testing Checklist

### Unit Tests
- [ ] SatisfactionCalculator all states
- [ ] SatisfactionCalculator hysteresis
- [ ] HybridValveController all paths
- [ ] HybridValveController edge cases

### Integration Tests
- [ ] Zone entity initialization
- [ ] Temperature change triggers valve decision
- [ ] Hybrid logic prevents overheating
- [ ] Main coordinator calculates correctly
- [ ] Safety coordinator enforces min valves

### End-to-End Tests
- [ ] Morning warmup scenario
- [ ] Single zone heating scenario
- [ ] All zones satisfied scenario
- [ ] 24-hour stability test
- [ ] Rapid temperature fluctuations

---

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage > 80%
- [ ] Documentation complete
- [ ] Example configurations tested

### Deployment
- [ ] Create release branch
- [ ] Tag version
- [ ] Build addon
- [ ] Test on fresh HA install
- [ ] Monitor first 24 hours

### Post-Deployment
- [ ] Gather user feedback
- [ ] Monitor error logs
- [ ] Track metrics
- [ ] Iterate on issues

---

## Common Pitfalls to Avoid

### 1. Event Handling
❌ **Don't**: Use `asyncio.create_task()` in event handlers
✅ **Do**: Use `hass.async_create_task()`

❌ **Don't**: Assume event.data["new_state"] exists
✅ **Do**: Validate: `if new_state is None: return`

### 2. State Management
❌ **Don't**: Keep critical state only in memory
✅ **Do**: Write to Redis on every change

❌ **Don't**: Assume Redis is always available
✅ **Do**: Handle connection failures gracefully

### 3. Valve Control
❌ **Don't**: Allow rapid valve cycling
✅ **Do**: Enforce actuation delays

❌ **Don't**: Close last valve
✅ **Do**: Check minimum valves before closing

### 4. Error Handling
❌ **Don't**: Let exceptions crash zones
✅ **Do**: Catch all exceptions, log, continue

❌ **Don't**: Fail silently
✅ **Do**: Log errors clearly

---

## Performance Optimization

### Caching
- Cache main target for 5 seconds
- Cache zone list for 10 seconds
- Invalidate on writes

### Batch Operations
- Use Redis pipelines for multiple operations
- Batch state writes when possible

### Async/Await
- Never block in event handlers
- Use `async_timeout` for service calls
- Properly await all async operations

---

## Metrics to Track

### System Health
- Event processing time (target: < 100ms)
- Valve decision time (target: < 10ms)
- Redis operation time (target: < 50ms)
- Memory usage (target: < 50MB)

### Operational Metrics
- Valve actions per hour per zone
- State transitions per day
- Tier 1 vs Tier 2 closure ratio
- Safety coordinator interventions

### User Experience
- Time to first valve action after temp change
- Zone oscillation rate
- User configuration errors

---

## Debugging Guide

### Issue: Zone not responding to temperature changes

**Check**:
1. Event listener registered? (log in `async_added_to_hass`)
2. Temperature sensor entity exists?
3. Event handler being called? (add log at start)
4. Exception being thrown? (check logs)

### Issue: Valve not opening/closing

**Check**:
1. Hybrid logic decision (check logs for tier results)
2. Valve locked? (recent actuation)
3. Service call succeeding? (check HA service logs)
4. Entity ID correct?

### Issue: All valves closed (safety violation)

**Check**:
1. Safety coordinator running? (check last update time)
2. Fallback zone configured?
3. Redis state accurate? (check zone states)
4. Min valves setting correct?

---

## Next Steps

1. **Start Implementation**: Begin with Phase 1 (Core Logic)
2. **Test Incrementally**: Write tests as you implement
3. **Document Progress**: Keep implementation log
4. **Ask Questions**: Clarify any uncertainties before coding
5. **Review Often**: Check against design document

**Ready to begin implementation!**
