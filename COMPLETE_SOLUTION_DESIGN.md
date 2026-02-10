# Fully Autonomous Zones with Hybrid Valve Control - Complete Solution Design

## Executive Summary

This document describes a **complete from-scratch implementation** of an intelligent multi-zone HVAC climate control system for Home Assistant. The solution combines two sophisticated approaches:

1. **Fully Autonomous Zones Architecture**: Zones self-govern through event-driven Python code without external backend services
2. **Hybrid Valve Control Logic**: Two-tier decision system preventing overheating while optimizing comfort

**Key Innovation**: Each zone independently manages its own temperature and valve, using hybrid logic to make intelligent decisions about when to open/close valves based on both safety (temperature thresholds) and efficiency (deficit priorities).

---

## Problem Statement

### The Challenge

Multi-zone HVAC systems face several critical challenges:

1. **Single Main Thermostat**: Controls water temperature for entire system
2. **Multiple Independent Zones**: Each room needs different temperature
3. **Valve Safety**: Must ensure at least 1 valve always open (prevent pump damage)
4. **Overheating Risk**: When main climate boosts temperature for one cold zone, satisfied zones can overheat
5. **Complexity Management**: Need simple, maintainable solution without external services

### Real-World Example

```
Scenario: Morning warmup
Kitchen:  20°C current, 24°C target → UNDERHEATED (needs heat)
Bedroom:  21°C current, 21°C target → SATISFIED (comfortable)

Main Climate: 23°C → boosts to 25°C to heat kitchen

Problem: Bedroom receives 25°C water when it only needs 21°C
Result:  Bedroom overheats! ❌

Solution Needed: Smart valve control that:
- Keeps kitchen valve OPEN (needs heat) ✓
- CLOSES bedroom valve (would overheat) ✓
- Maintains system safety (1+ valve open) ✓
```

---

## Solution Overview

### Architecture: Fully Autonomous Zones

```
┌─────────────────────────────────────────────────────────┐
│              Home Assistant Core                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │    Multizone Climate Custom Integration          │  │
│  │                                                   │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  Zone Climate Entities                     │  │  │
│  │  │  (One per zone - autonomous & self-gov)    │  │  │
│  │  │                                            │  │  │
│  │  │  Each Zone Has:                           │  │  │
│  │  │  ├─ Event Listener (temp sensor)          │  │  │
│  │  │  ├─ Satisfaction State Machine            │  │  │
│  │  │  ├─ Hybrid Valve Controller               │  │  │
│  │  │  ├─ Valve Manager                         │  │  │
│  │  │  └─ Redis State Writer                    │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  │                                                   │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  Main Climate Coordinator                  │  │  │
│  │  │  (Periodic - calculates main target)      │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  │                                                   │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  Safety Coordinator                        │  │  │
│  │  │  (Ensures min valves open)                 │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
                        │ State Persistence
                        ▼
            ┌───────────────────────┐
            │       Redis           │
            │  (Simple state store) │
            └───────────────────────┘
```

### Hybrid Valve Control Logic

**Two-Tier Decision System** for satisfied zones:

```python
def determine_valve_action(zone, main_target, underheated_zones):
    """Hybrid two-tier decision for satisfied zones."""
    
    if zone.satisfaction == "underheated":
        return OPEN  # Always open
    
    if zone.satisfaction == "overheated":
        return CLOSE  # Always close
    
    if zone.satisfaction == "satisfied":
        if not underheated_zones:
            return OPEN  # No competition, maintain temp
        
        # TIER 1: Temperature Safety Check
        overheat_threshold = zone.target + zone.upper_offset
        if main_target > overheat_threshold:
            return CLOSE  # Would overheat - safety first!
        
        # TIER 2: Deficit Magnitude Check
        max_deficit = max(z.deficit for z in underheated_zones)
        if max_deficit > zone.deficit_threshold:
            return CLOSE  # Large deficit - prioritize heating
        
        return OPEN  # Safe to maintain both
```

---

## Component Design

### 1. Zone Climate Entity (Core Component)

**Purpose**: Self-governing climate entity for each zone

**Key Features**:
- Event-driven (reacts to temperature sensor changes)
- Autonomous valve control
- Hybrid decision logic
- State persistence to Redis

**Implementation**:

```python
class AutonomousZoneClimate(ClimateEntity):
    """
    Fully autonomous zone climate entity with hybrid valve control.
    
    This entity:
    1. Listens to temperature sensor state changes
    2. Calculates satisfaction state (underheated/satisfied/overheated)
    3. Uses hybrid logic to decide valve action
    4. Executes valve control directly
    5. Writes state to Redis for coordination
    """
    
    def __init__(
        self,
        hass,
        zone_id: str,
        name: str,
        temp_sensor_id: str,
        valve_switch_id: str,
        target_temperature: float,
        config: dict,
    ):
        """Initialize autonomous zone."""
        self.hass = hass
        self.zone_id = zone_id
        self.name = name
        self.temp_sensor_id = temp_sensor_id
        self.valve_switch_id = valve_switch_id
        self._target_temperature = target_temperature
        
        # Configuration parameters
        self.lower_offset = config.get("lower_offset", 0.0)
        self.upper_offset = config.get("upper_offset", 0.3)
        self.satisfaction_epsilon = config.get("satisfaction_epsilon", 0.1)
        self.deficit_threshold = config.get("deficit_threshold", 1.0)
        self.valve_delay = config.get("valve_delay", 120)
        self.is_fallback = config.get("is_fallback", False)
        
        # Internal state
        self._current_temperature = None
        self._satisfaction = "unknown"
        self._valve_state = "unknown"
        self._last_valve_action_time = 0
        
        # Sub-components
        self.satisfaction_calculator = SatisfactionCalculator(
            lower_offset=self.lower_offset,
            upper_offset=self.upper_offset,
            satisfaction_epsilon=self.satisfaction_epsilon,
        )
        self.hybrid_controller = HybridValveController(
            deficit_threshold=self.deficit_threshold,
        )
        self.valve_manager = ValveManager(
            hass=hass,
            valve_switch_id=self.valve_switch_id,
            valve_delay=self.valve_delay,
        )
        self.redis_client = RedisClient(hass)
    
    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        
        # Register event listener for temperature sensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.temp_sensor_id],
                self._handle_temperature_change,
            )
        )
        
        # Initialize current temperature
        temp_state = self.hass.states.get(self.temp_sensor_id)
        if temp_state:
            try:
                self._current_temperature = float(temp_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid initial temperature for {self.zone_id}")
        
        # Write initial state to Redis
        await self._write_state_to_redis()
        
        _LOGGER.info(f"Autonomous zone {self.zone_id} initialized")
    
    async def _handle_temperature_change(self, event):
        """
        Handle temperature sensor state change - CORE AUTONOMOUS LOGIC.
        
        This is the heart of the autonomous zone:
        1. Update current temperature
        2. Calculate satisfaction state
        3. Make valve decision using hybrid logic
        4. Execute valve action
        5. Update Redis state
        """
        
        # Validate event
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if new_state is None:
            return
        
        if old_state and old_state.state == new_state.state:
            return  # No actual change
        
        # Extract new temperature
        try:
            new_temp = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(f"Invalid temperature value for {self.zone_id}: {new_state.state}")
            return
        
        old_temp = self._current_temperature
        self._current_temperature = new_temp
        
        _LOGGER.debug(
            f"Zone {self.zone_id}: Temperature changed {old_temp}°C → {new_temp}°C"
        )
        
        # Calculate new satisfaction state
        old_satisfaction = self._satisfaction
        self._satisfaction = self.satisfaction_calculator.calculate(
            current_temp=new_temp,
            target_temp=self._target_temperature,
            previous_satisfaction=old_satisfaction,
        )
        
        if self._satisfaction != old_satisfaction:
            _LOGGER.info(
                f"Zone {self.zone_id}: Satisfaction changed {old_satisfaction} → {self._satisfaction}"
            )
        
        # Determine valve action using hybrid logic
        valve_action = await self._determine_valve_action()
        
        # Execute valve action if needed
        if valve_action:
            await self._execute_valve_action(valve_action)
        
        # Write updated state to Redis
        await self._write_state_to_redis()
    
    async def _determine_valve_action(self) -> Optional[str]:
        """
        Determine valve action using hybrid logic.
        
        Returns:
            "open", "close", or None (no action)
        """
        
        # Get current valve state
        current_valve_state = await self._get_current_valve_state()
        
        # Check if valve is locked (recently actuated)
        if await self._is_valve_locked():
            _LOGGER.debug(f"Zone {self.zone_id}: Valve locked, skipping action")
            return None
        
        # Get main climate target from Redis
        main_target = await self._get_main_target_from_redis()
        
        # Get underheated zones from Redis
        underheated_zones = await self._get_underheated_zones_from_redis()
        
        # Use hybrid controller to decide
        desired_action = self.hybrid_controller.determine_action(
            satisfaction=self._satisfaction,
            zone_target=self._target_temperature,
            upper_offset=self.upper_offset,
            main_target_temp=main_target,
            underheated_zones=underheated_zones,
        )
        
        # Only return action if state needs to change
        if desired_action == "open" and current_valve_state != "open":
            return "open"
        elif desired_action == "close" and current_valve_state != "closed":
            return "close"
        
        return None
    
    async def _execute_valve_action(self, action: str):
        """Execute valve open/close action with safety checks."""
        
        # Safety check: ensure minimum valves remain open
        if action == "close":
            can_close = await self._check_can_close_valve()
            if not can_close:
                _LOGGER.warning(
                    f"Zone {self.zone_id}: Cannot close valve - would violate min valves open"
                )
                return
        
        # Execute through valve manager
        success = await self.valve_manager.execute_action(action, self.zone_id)
        
        if success:
            self._valve_state = "opening" if action == "open" else "closing"
            self._last_valve_action_time = time.time()
            
            _LOGGER.info(f"Zone {self.zone_id}: Valve action '{action}' executed")
        else:
            _LOGGER.error(f"Zone {self.zone_id}: Valve action '{action}' failed")
    
    async def _write_state_to_redis(self):
        """Write current zone state to Redis for coordination."""
        
        state = {
            "zone_id": self.zone_id,
            "name": self.name,
            "current_temperature": self._current_temperature,
            "target_temperature": self._target_temperature,
            "satisfaction": self._satisfaction,
            "valve_state": self._valve_state,
            "is_fallback": self.is_fallback,
            "enabled": True,
            "updated_at": time.time(),
        }
        
        await self.redis_client.set_zone_state(self.zone_id, state)
    
    async def _get_main_target_from_redis(self) -> float:
        """Get current main climate target temperature from Redis."""
        main_state = await self.redis_client.get_main_climate_state()
        return main_state.get("target_temperature", 23.0)  # Fallback
    
    async def _get_underheated_zones_from_redis(self) -> list:
        """Get list of underheated zones from Redis."""
        all_zones = await self.redis_client.get_all_zones()
        return [
            {
                "zone_id": z["zone_id"],
                "deficit": z["target_temperature"] - z["current_temperature"],
            }
            for z in all_zones
            if z.get("satisfaction") == "underheated"
        ]
    
    async def _check_can_close_valve(self) -> bool:
        """Check if this valve can be closed without violating safety."""
        
        if self.is_fallback:
            # Fallback zones should not close if they're the only open valve
            open_count = await self._count_open_valves()
            if open_count <= 1:
                return False
        
        # Check minimum valves open requirement
        min_valves = await self.redis_client.get_config("min_valves_open", 1)
        open_count = await self._count_open_valves()
        
        # Can close if there will still be enough open valves
        return (open_count - 1) >= min_valves
    
    async def _count_open_valves(self) -> int:
        """Count currently open valves across all zones."""
        all_zones = await self.redis_client.get_all_zones()
        return sum(
            1 for z in all_zones 
            if z.get("valve_state") in ["open", "opening"]
        )
    
    async def _get_current_valve_state(self) -> str:
        """Get current valve state from HA."""
        valve_state = self.hass.states.get(self.valve_switch_id)
        if valve_state:
            return "open" if valve_state.state == "on" else "closed"
        return "unknown"
    
    async def _is_valve_locked(self) -> bool:
        """Check if valve is locked due to recent actuation."""
        time_since_last = time.time() - self._last_valve_action_time
        return time_since_last < self.valve_delay
    
    # ClimateEntity properties
    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._name
    
    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS
    
    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature
    
    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature
    
    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return HVACMode.HEAT  # Heating only for now
    
    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return [HVACMode.HEAT, HVACMode.OFF]
    
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = temperature
            await self._write_state_to_redis()
            
            # Trigger immediate re-evaluation
            await self._handle_temperature_change(
                {"data": {
                    "new_state": self.hass.states.get(self.temp_sensor_id),
                    "old_state": None,
                }}
            )
```

---

### 2. Satisfaction State Calculator

**Purpose**: Determine zone satisfaction state with hysteresis

```python
class SatisfactionCalculator:
    """
    Calculate zone satisfaction state with hysteresis.
    
    States:
    - underheated: temp < (target - lower_offset)
    - satisfied: within acceptable range
    - overheated: temp > (target + upper_offset)
    
    Uses satisfaction_epsilon to prevent oscillation.
    """
    
    def __init__(
        self,
        lower_offset: float = 0.0,
        upper_offset: float = 0.3,
        satisfaction_epsilon: float = 0.1,
    ):
        self.lower_offset = lower_offset
        self.upper_offset = upper_offset
        self.satisfaction_epsilon = satisfaction_epsilon
        
        # Validation
        if satisfaction_epsilon >= min(lower_offset, upper_offset) - 0.1:
            raise ValueError("satisfaction_epsilon must be at least 0.1 less than min offset")
    
    def calculate(
        self,
        current_temp: float,
        target_temp: float,
        previous_satisfaction: str,
    ) -> str:
        """
        Calculate new satisfaction state with hysteresis.
        
        Hysteresis prevents rapid state changes:
        - Once underheated, must reach (target + epsilon) to become satisfied
        - Once overheated, must reach (target - epsilon) to become satisfied
        """
        
        # Calculate thresholds
        underheated_threshold = target_temp - self.lower_offset
        overheated_threshold = target_temp + self.upper_offset
        
        # Direct state changes (clear thresholds)
        if current_temp < underheated_threshold:
            return "underheated"
        
        if current_temp > overheated_threshold:
            return "overheated"
        
        # Hysteresis zone - depends on previous state
        if previous_satisfaction == "underheated":
            # Must reach target + epsilon to become satisfied
            if current_temp >= (target_temp + self.satisfaction_epsilon):
                return "satisfied"
            return "underheated"
        
        elif previous_satisfaction == "overheated":
            # Must reach target - epsilon to become satisfied
            if current_temp <= (target_temp - self.satisfaction_epsilon):
                return "satisfied"
            return "overheated"
        
        # Already satisfied or unknown - stay satisfied if in range
        return "satisfied"
```

---

### 3. Hybrid Valve Controller

**Purpose**: Two-tier decision logic for valve control

```python
class HybridValveController:
    """
    Hybrid valve controller with two-tier decision logic.
    
    Tier 1: Temperature Safety
    - Prevents overheating of satisfied zones
    - Closes valve if main_target > (zone_target + upper_offset)
    
    Tier 2: Deficit Magnitude
    - Optimizes heat distribution
    - Closes valve if max_deficit > threshold
    """
    
    def __init__(self, deficit_threshold: float = 1.0):
        self.deficit_threshold = deficit_threshold
    
    def determine_action(
        self,
        satisfaction: str,
        zone_target: float,
        upper_offset: float,
        main_target_temp: float,
        underheated_zones: list,
    ) -> str:
        """
        Determine valve action using hybrid logic.
        
        Returns:
            "open" or "close"
        """
        
        # Simple cases - no hybrid logic needed
        if satisfaction == "underheated":
            return "open"
        
        if satisfaction == "overheated":
            return "close"
        
        # Satisfied zone - apply hybrid logic
        if satisfaction == "satisfied":
            # No competition - maintain temperature
            if not underheated_zones:
                return "open"
            
            # TIER 1: Temperature Safety Check
            overheat_threshold = zone_target + upper_offset
            
            if main_target_temp > overheat_threshold:
                # Would overheat - close immediately
                _LOGGER.debug(
                    f"TIER 1: Closing valve. "
                    f"Main {main_target_temp:.1f}°C > threshold {overheat_threshold:.1f}°C"
                )
                return "close"
            
            # TIER 2: Deficit Magnitude Check
            max_deficit = max(
                zone.get("deficit", 0) 
                for zone in underheated_zones
            )
            
            if max_deficit > self.deficit_threshold:
                # Large deficit - prioritize underheated zones
                _LOGGER.debug(
                    f"TIER 2: Closing valve. "
                    f"Max deficit {max_deficit:.1f}°C > threshold {self.deficit_threshold:.1f}°C"
                )
                return "close"
            
            # Both checks passed - safe to keep open
            _LOGGER.debug(
                f"Hybrid checks passed. Keeping valve open. "
                f"Main {main_target_temp:.1f}°C ≤ {overheat_threshold:.1f}°C, "
                f"deficit {max_deficit:.1f}°C ≤ {self.deficit_threshold:.1f}°C"
            )
            return "open"
        
        # Unknown state - default to safe (open)
        return "open"
```

---

### 4. Main Climate Coordinator

**Purpose**: Periodic calculation of main climate target temperature

```python
class MainClimateCoordinator(DataUpdateCoordinator):
    """
    Coordinator that periodically calculates main climate target.
    
    Does NOT control zones - zones are autonomous.
    This just calculates what temperature the main climate should be.
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        redis_client: RedisClient,
        main_climate_entity_id: str,
        update_interval: int = 30,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Main Climate Coordinator",
            update_interval=timedelta(seconds=update_interval),
        )
        self.redis_client = redis_client
        self.main_climate_entity_id = main_climate_entity_id
    
    async def _async_update_data(self):
        """Calculate and update main climate target."""
        
        try:
            # Get all zones from Redis
            zones = await self.redis_client.get_all_zones()
            
            if not zones:
                _LOGGER.warning("No zones found for main target calculation")
                return
            
            # Get main climate current temperature
            main_state = self.hass.states.get(self.main_climate_entity_id)
            if not main_state:
                _LOGGER.error(f"Main climate entity not found: {self.main_climate_entity_id}")
                return
            
            try:
                main_current_temp = float(main_state.attributes.get("current_temperature", 23.0))
            except (ValueError, TypeError):
                main_current_temp = 23.0
            
            # Calculate main target using deficit-based approach
            main_target = self._calculate_main_target_heating(
                zones=zones,
                main_current_temp=main_current_temp,
            )
            
            # Write to Redis
            await self.redis_client.set_main_climate_state({
                "target_temperature": main_target,
                "current_temperature": main_current_temp,
                "updated_at": time.time(),
            })
            
            # Update main climate entity
            await self._update_main_climate_entity(main_target)
            
            _LOGGER.info(f"Main target calculated: {main_target:.1f}°C")
            
        except Exception as e:
            _LOGGER.error(f"Error in main climate coordinator: {e}", exc_info=True)
            raise
    
    def _calculate_main_target_heating(
        self,
        zones: list,
        main_current_temp: float,
    ) -> float:
        """
        Calculate main climate target for heating mode.
        
        Algorithm:
        - If any zone underheated: main_current + max_zone_deficit
        - If all satisfied: average of zone targets
        - If all overheated: minimum of zone targets
        """
        
        # Filter enabled zones
        enabled_zones = [z for z in zones if z.get("enabled", True)]
        
        if not enabled_zones:
            return 23.0  # Default fallback
        
        # Categorize zones
        underheated = [z for z in enabled_zones if z.get("satisfaction") == "underheated"]
        satisfied = [z for z in enabled_zones if z.get("satisfaction") == "satisfied"]
        overheated = [z for z in enabled_zones if z.get("satisfaction") == "overheated"]
        
        # HEATING MODE: Any underheated zones
        if underheated:
            # Calculate maximum deficit
            max_deficit = 0.0
            for zone in underheated:
                current = zone.get("current_temperature", 0)
                target = zone.get("target_temperature", 0)
                if current and target:
                    deficit = max(0.0, target - current)
                    max_deficit = max(max_deficit, deficit)
            
            # Main target = current + max deficit
            main_target = main_current_temp + max_deficit
            
            _LOGGER.debug(
                f"HEATING MODE: {len(underheated)} underheated zones, "
                f"max deficit {max_deficit:.1f}°C, "
                f"target {main_target:.1f}°C"
            )
            
            return round(main_target * 2) / 2  # Round to 0.5°C
        
        # MAINTENANCE MODE: All satisfied
        elif satisfied:
            # Average of satisfied zone targets
            targets = [z["target_temperature"] for z in satisfied]
            main_target = sum(targets) / len(targets)
            
            _LOGGER.debug(
                f"MAINTENANCE MODE: All {len(satisfied)} zones satisfied, "
                f"target {main_target:.1f}°C"
            )
            
            return round(main_target * 2) / 2
        
        # IDLE MODE: All overheated
        elif overheated:
            # Minimum of overheated zone targets
            targets = [z["target_temperature"] for z in overheated]
            main_target = min(targets)
            
            _LOGGER.debug(
                f"IDLE MODE: All {len(overheated)} zones overheated, "
                f"target {main_target:.1f}°C"
            )
            
            return round(main_target * 2) / 2
        
        # Fallback
        return 23.0
    
    async def _update_main_climate_entity(self, target_temp: float):
        """Update the main climate entity with new target."""
        
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self.main_climate_entity_id,
                    "temperature": target_temp,
                },
                blocking=True,
            )
            _LOGGER.debug(f"Main climate updated to {target_temp:.1f}°C")
        except Exception as e:
            _LOGGER.error(f"Failed to update main climate: {e}")
```

---

### 5. Safety Coordinator

**Purpose**: Ensure minimum valves always open

```python
class SafetyCoordinator(DataUpdateCoordinator):
    """
    Safety coordinator ensures minimum valves remain open.
    
    This is a backup safety measure. Normal operation should
    maintain proper valve states through autonomous zone logic.
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        redis_client: RedisClient,
        min_valves_open: int = 1,
        check_interval: int = 60,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Safety Coordinator",
            update_interval=timedelta(seconds=check_interval),
        )
        self.redis_client = redis_client
        self.min_valves_open = min_valves_open
    
    async def _async_update_data(self):
        """Check and enforce minimum valves open."""
        
        try:
            # Get all zones
            zones = await self.redis_client.get_all_zones()
            
            if not zones:
                return
            
            # Count open valves
            open_valves = [
                z for z in zones 
                if z.get("valve_state") in ["open", "opening"]
            ]
            
            open_count = len(open_valves)
            
            _LOGGER.debug(f"Safety check: {open_count} valves open (min: {self.min_valves_open})")
            
            # Check if minimum met
            if open_count < self.min_valves_open:
                _LOGGER.warning(
                    f"SAFETY VIOLATION: Only {open_count} valves open, "
                    f"need {self.min_valves_open}"
                )
                
                # Find fallback zones to open
                fallback_zones = [
                    z for z in zones 
                    if z.get("is_fallback", False)
                ]
                
                if fallback_zones:
                    # Force open first fallback zone
                    fallback = fallback_zones[0]
                    await self._force_open_valve(fallback["zone_id"])
                else:
                    # No fallback - open first available zone
                    if zones:
                        await self._force_open_valve(zones[0]["zone_id"])
            
        except Exception as e:
            _LOGGER.error(f"Error in safety coordinator: {e}", exc_info=True)
    
    async def _force_open_valve(self, zone_id: str):
        """Force a valve open for safety."""
        
        _LOGGER.warning(f"SAFETY: Force opening valve for zone {zone_id}")
        
        # This would trigger a service call to open the valve
        # Implementation depends on how zones expose their valve control
        await self.hass.services.async_call(
            "multizone_climate",
            "force_open_valve",
            {"zone_id": zone_id},
        )
```

---

## File Structure

```
custom_components/multizone_climate/
├── __init__.py                      # Integration setup
├── manifest.json                    # Integration metadata
├── config_flow.py                   # Config flow (zone setup)
├── const.py                         # Constants
├── climate.py                       # AutonomousZoneClimate entity
├── coordinator.py                   # Main & Safety coordinators
│
├── core/
│   ├── __init__.py
│   ├── satisfaction.py              # SatisfactionCalculator
│   ├── hybrid_valve.py              # HybridValveController
│   ├── valve_manager.py             # ValveManager
│   └── redis_client.py              # RedisClient
│
└── services.yaml                    # Service definitions

addon/
├── config.yaml                      # Addon configuration
├── Dockerfile                       # Redis-only container
└── rootfs/
    └── etc/
        └── s6-overlay/
            └── s6-rc.d/
                └── redis/           # Redis service
```

---

## Configuration

### Integration Configuration (Config Flow)

**Step 1: Select Main Climate**
```yaml
main_climate_entity_id: climate.main_thermostat
```

**Step 2: Configure Zones** (repeatable)
```yaml
zones:
  - zone_id: bedroom
    name: Bedroom
    temp_sensor: sensor.bedroom_temperature
    valve_switch: switch.bedroom_valve
    target_temperature: 21.0
    lower_offset: 0.0
    upper_offset: 0.3
    satisfaction_epsilon: 0.1
    deficit_threshold: 1.0
    valve_delay: 120
    is_fallback: false
```

**Step 3: Global Settings**
```yaml
min_valves_open: 1
main_coordinator_interval: 30  # seconds
safety_check_interval: 60      # seconds
```

---

## Redis Data Structure

### Zone State
```
Key: multizone:zone:{zone_id}
Type: Hash

{
  "zone_id": "bedroom",
  "name": "Bedroom",
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
```
Key: multizone:main_climate
Type: Hash

{
  "target_temperature": 23.5,
  "current_temperature": 23.0,
  "updated_at": 1707565200.0
}
```

### Configuration
```
Key: multizone:config
Type: Hash

{
  "min_valves_open": 1,
  "main_coordinator_interval": 30,
  "safety_check_interval": 60
}
```

---

## Critical Implementation Tasks

### 1. Event-Driven Architecture
- ✅ Use `async_track_state_change_event` for temperature sensors
- ✅ Use `hass.async_create_task()` for async operations
- ✅ Validate event.data contains new_state before processing
- ✅ Check if state actually changed (old != new)

### 2. Hybrid Valve Logic
- ✅ Implement Tier 1 (temperature safety) first
- ✅ Add Tier 2 (deficit magnitude) second
- ✅ Ensure underheated zones ALWAYS open valves
- ✅ Ensure overheated zones ALWAYS close valves

### 3. Safety Mechanisms
- ✅ Valve actuation delay (prevent rapid cycling)
- ✅ Minimum valves open enforcement
- ✅ Fallback valve designation
- ✅ Safety coordinator as backup

### 4. State Management
- ✅ Write zone state to Redis on every temperature change
- ✅ Cache main target locally (5s TTL)
- ✅ Handle Redis connection failures gracefully
- ✅ Use last known values as fallback

### 5. Error Handling
- ✅ Invalid sensor values
- ✅ Missing entities
- ✅ Redis unavailable
- ✅ Service call failures
- ✅ All errors logged, never crash zones

---

## Security Requirements

### 1. Input Validation
- ✅ Validate all temperature values (range: 0-50°C)
- ✅ Validate entity IDs exist before use
- ✅ Validate configuration parameters
- ✅ Sanitize zone IDs (alphanumeric + underscore only)

### 2. Redis Security
- ✅ Optional password authentication
- ✅ Network isolation (localhost only by default)
- ✅ No sensitive data in Redis (only config/state)

### 3. Service Call Security
- ✅ Verify entity_id ownership (belongs to this integration)
- ✅ Rate limiting on valve operations
- ✅ Audit log of all valve actions

---

## Testing Strategy

### Unit Tests

```python
# test_satisfaction.py
def test_satisfaction_underheated():
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    result = calc.calculate(current_temp=20.0, target_temp=21.0, previous_satisfaction="unknown")
    assert result == "underheated"

def test_satisfaction_hysteresis():
    calc = SatisfactionCalculator(lower_offset=0.0, upper_offset=0.3, satisfaction_epsilon=0.1)
    # Was underheated, now at target - should still be underheated
    result = calc.calculate(current_temp=21.0, target_temp=21.0, previous_satisfaction="underheated")
    assert result == "underheated"
    # Must reach target + epsilon to become satisfied
    result = calc.calculate(current_temp=21.1, target_temp=21.0, previous_satisfaction="underheated")
    assert result == "satisfied"

# test_hybrid_valve.py
def test_tier1_temperature_safety():
    controller = HybridValveController(deficit_threshold=1.0)
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=21.0,
        upper_offset=0.3,
        main_target_temp=25.0,  # > 21.3
        underheated_zones=[{"zone_id": "kitchen", "deficit": 2.0}],
    )
    assert result == "close"  # Would overheat

def test_tier2_deficit_magnitude():
    controller = HybridValveController(deficit_threshold=1.0)
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=24.0,
        upper_offset=0.3,
        main_target_temp=24.0,  # Safe temp
        underheated_zones=[{"zone_id": "kitchen", "deficit": 2.0}],  # > 1.0
    )
    assert result == "close"  # Large deficit

def test_both_checks_pass():
    controller = HybridValveController(deficit_threshold=1.0)
    result = controller.determine_action(
        satisfaction="satisfied",
        zone_target=24.0,
        upper_offset=0.3,
        main_target_temp=24.0,  # Safe temp
        underheated_zones=[{"zone_id": "kitchen", "deficit": 0.5}],  # < 1.0
    )
    assert result == "open"  # Both checks pass
```

### Integration Tests

```python
# test_autonomous_zone.py
async def test_temperature_change_triggers_valve_action(hass):
    """Test that temp change triggers autonomous valve decision."""
    zone = AutonomousZoneClimate(...)
    await zone.async_added_to_hass()
    
    # Simulate temperature drop
    hass.states.async_set("sensor.bedroom_temp", "20.0")
    await hass.async_block_till_done()
    
    # Should trigger underheated → open valve
    assert zone._satisfaction == "underheated"
    # Verify valve open service was called
    assert len(hass.services.async_call.mock_calls) > 0

async def test_hybrid_logic_prevents_overheating(hass, redis_client):
    """Test that hybrid logic closes satisfied zone when would overheat."""
    zone = AutonomousZoneClimate(...)
    
    # Set up scenario: satisfied zone, underheated kitchen boosting main temp
    redis_client.set_main_climate_state({"target_temperature": 25.0})
    redis_client.set_zone_state("kitchen", {"satisfaction": "underheated", "deficit": 2.0})
    
    # Bedroom at 21°C satisfied, would overheat with 25°C water
    hass.states.async_set("sensor.bedroom_temp", "21.0")
    await hass.async_block_till_done()
    
    # Should close valve (Tier 1 check fails)
    # Verify valve close service was called
```

---

## Deployment Plan

### Phase 1: Core Components (Week 1)
- [ ] Create `AutonomousZoneClimate` entity
- [ ] Implement `SatisfactionCalculator`
- [ ] Implement `HybridValveController`
- [ ] Basic `RedisClient`
- [ ] Unit tests

### Phase 2: Coordinators (Week 2)
- [ ] Implement `MainClimateCoordinator`
- [ ] Implement `SafetyCoordinator`
- [ ] Integration tests
- [ ] Error handling

### Phase 3: Config Flow (Week 3)
- [ ] Multi-step config flow
- [ ] Zone management (add/remove)
- [ ] Validation
- [ ] UI testing

### Phase 4: Addon (Week 4)
- [ ] Redis container
- [ ] Component auto-install
- [ ] Notification system
- [ ] End-to-end testing

### Phase 5: Documentation & Release (Week 5)
- [ ] User documentation
- [ ] API documentation
- [ ] Example configurations
- [ ] Beta release

---

## Migration from Existing Implementation

### Differences from Main Branch

**Architecture Changes**:
- ❌ Remove: Go backend service
- ❌ Remove: Coordinator polling for commands
- ❌ Remove: Job queue system
- ✅ Add: Event-driven zone entities
- ✅ Add: Hybrid valve controller
- ✅ Keep: Redis for state storage
- ✅ Keep: Config flow

**Code Reuse Opportunities**:
- ✓ Config flow structure
- ✓ Redis client patterns
- ✓ Satisfaction state machine concept
- ✓ Main target calculation algorithm
- ✓ Valve safety checks

**Breaking Changes**:
- Zones now manage themselves (no backend commands)
- Different valve decision logic (hybrid vs simple)
- Simpler addon (Redis only)

---

## Success Criteria

### Functional
- ✅ Zones respond to temperature changes < 5 seconds
- ✅ Hybrid logic prevents overheating in all test scenarios
- ✅ Minimum valves always maintained
- ✅ System stable for 48+ hours continuous operation
- ✅ No valve cycling (> 10 actions/hour/zone indicates problem)

### Performance
- ✅ Temperature event processing < 100ms
- ✅ Valve decision logic < 10ms
- ✅ Redis operations < 50ms
- ✅ Memory usage < 50MB for integration
- ✅ CPU usage < 5% average

### User Experience
- ✅ Easy configuration (< 5 minutes)
- ✅ Clear status indicators
- ✅ Helpful error messages
- ✅ Responsive UI

---

## Questions to Resolve

### IMPLEMENTATION READY ✅

All architectural decisions have been made:
- ✅ Architecture: Fully Autonomous Zones
- ✅ Valve Logic: Hybrid (Tier 1 + Tier 2)
- ✅ Backend: Redis only (no Go service)
- ✅ Event Model: Temperature sensor state changes
- ✅ Coordination: Periodic main temp calculation
- ✅ Safety: Dual enforcement (zones + coordinator)

**No blocking questions remain. Ready for implementation.**

---

## Next Steps for Implementation Agent

1. **Start with Core**: Implement `SatisfactionCalculator` and `HybridValveController` first (pure logic, easy to test)

2. **Build Zone Entity**: Create `AutonomousZoneClimate` with event handling

3. **Add Coordinators**: Implement `MainClimateCoordinator` and `SafetyCoordinator`

4. **Wire Everything**: Connect components in `__init__.py`

5. **Test Incrementally**: Unit tests → Integration tests → End-to-end

6. **Document As You Go**: Code comments, docstrings, user docs

---

**This document provides complete specifications for building the system from scratch. All design decisions are made. Ready for implementation.**
