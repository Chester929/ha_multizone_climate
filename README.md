# ha_multizone_climate
Home Assistant Automation integration to better manage heat zones.

# What's the Issue
I have an HVAC unit driven by one thermostat using a heating curve to calculate the correct temperature in pipes.
I would like to manage temperature per room using sensors and valve controllers.
The HVAC is missing a circulating line, so there has to be at least one valve still open.

## Main Climate Unit and Thermostat
I have an HVAC unit which is controlled by one thermostat through physical cables.
This thermostat is placed in the corridor and has its own temperature sensor.
The HVAC unit uses this thermostat's temperature sensor alongside an outside temperature sensor to calculate how to heat water to heat or maintain the inside temperature using a "heating curve".
Heating curve is configured in the UNIT: "heating curve deviation (base)" = 15.0°
                                        "increase" = 0.5
That means when outside temperature is 25°C, the water temperature in heating pipes is 0°C; when outside is 15°C, the water in pipes is 20°C.
The HVAC also provides cooling when outside temperature is higher than the target inside temperature, but does not have a sensor for it.
We can change these two options to get better results in the future, but that's a unit configuration matter.

The thermostat can be controlled remotely through a cloud API (it has network connection over WiFi to connect to the cloud).
I have a smart home driven by Home Assistant. I already have a custom component which produces a custom climate entity to control the thermostat through API (cloud). You can find this custom component there https://github.com/Chester929/remeha_home_by_chester.
I can control via API the target temperature and HVAC mode (OFF (Anti-Freeze), Manual, Scheduler)

There is also another climate component to control the DWH (boiler) to heat hot water for the house. But it is a separate feature of the HVAC unit and has its own control entity.
The boiler is not part of this issue.

## Heat Zones
I already have temperature sensors in my other rooms integrated with Home Assistant.
There are also heat pipe valves (open/close) for each room controlled remotely and integrated with Home Assistant via switch entities.

# What's the Goal
I would like to implement a Home Assistant integration which will effectively manage the heating system via valve controllers and temperature sensors, targeting the right temperature on the main HVAC thermostat based on configured target temperatures for different rooms set by the user.
It has to be clean code, nice, effective, fast, and safe! Also this component should be able to be installed over HACS into Home Assistant.

## Project Architecture draft
  - MAIN CLIMATE DEVICE (Main Climate Entity from config entry)
    - Temperature Sensor - Main climate target temperature
    - Temperature Sensor - Main climate current temperature
    - Temperature Sensor - Outdoor temperature
    - Climate HVAC mode (OFF (Anti-Freeze), MANUAL, SCHEDULING)
    - State (OFF, HEATING, COOLING)
      - Cooling when main climate target temperature is lower than outdoor temperature
      - Off/on state
        - Manual switch on/off
        - When there are not any climate zones present yet, switch is not editable and is set to off
        - When HVAC mode is OFF, then on/off switch is not editable and is set to off
        - When off, climate zones are not managed by multizone feature, but every climate zone just controls its own valve by its own target and current temperature
  - CLIMATE ZONE SUBDEVICES (Climate device per room)
    - Name
    - State (off, underheated, satisfied, overheated) resp. (off, overcooled, satisfied, undercooled) when cooling
    - Temperature sensor
    - Valve switch
    - Target change threshold
    - Opening offset below target
    - Closing offset above target
  - REDIS CONFIG (Redis required)
   - host
   - port
   - credentials
  - CONFIG
    - All zones satisfied temperature target
    - Minimum valves open
    - Main climate min/max temperature
    - Main climate target temperature change threshold
    - Physical valve opening/closing delay
  - **CORE LOGIC
    - Helper methods respecting config described later
  - BACKGROUND ASYNC JOBS (3 jobs)
    - Update valves
      - Invoked by "Update main target temperature" automation
      - Job identifier (used for debugging and job status)
      - Run core logic inside to manage physical valves
    - Calculate main target temperature
      - Invoked by "Update main target temperature" automation
      - Job identifier (used for debugging and job status)
      - Run core logic inside to calculate temperature
    - Safety valve check
      - Invoked by "Safety valve check" automation
      - Job identifier (used for debugging and job status)
      - Run core logic inside to check minimum valves open
  - AUTOMATIONS (2 automations - Listens to events or time entity and invokes async job)
    - Update main target temperature
      - Invoked only when one (or more) of zones temperature or target temperature has been changed
      - Add "Calculate main target temperature" async job with current parameters into its process queue
      - Add "Update valves" async job with current params into its process queue
    - Safety valve check
      - Invoked every half of "Physical valve opening/closing delay" configured time (if configured delay is 0, then every 1m)
      - Directly invoke "Safety valve check" async job
  - COORDINATOR (runs every 15s)
    - Reads current entities data through core logic Redis client and:
      - Updates sensors
      - Updates 
    - Dequeue "Update valves" background async job from its queue and invoke it (if any in the queue and no other running)
    - Dequeue "Calculate main target temperature" background async job from its queue and invoke it (if any in the queue and no other running)
 - LOGGER (Logging)
   - INFO
   - WARN
   - ERROR
   - DEBUG
 - LOCALS (Translations (en, cz, sk, pl))
  - TESTS
    - Every single background job test with different scenarios (parameters)
    - Coordinator test
    - Core logic test
    - Home Assistant integration test per each entity (sensor, climate, etc)
 - LINTNERS (Code quality and security checks)
 - DOCUMENTATION
 - FRONTEND (cool and user friendly lovelace cards and dashboards to monitor sensors and manage climate entities)


## **Core Logic
Initializes and holds a Redis client instance to read global config and entities data.

### Find Main Climate Target Temperature
Inputs:
  - Main climate
    - current temperature
    - current target temperature
  - Changed climate zones:
    - current temperature
    - target temperature
    - valve switch
   
Steps:
  - Fetch config from Redis
  - Fetch data from Redis
  - Calculate target temperature
  - hass.service.call to update main climate entity target temperature
  - Update data to Redis 

### Update Valves
Inputs:
  - Main climate
    - current temperature
    - current target temperature
  - Valve Fallback Zone
  - All climate zones
    - current temperature
    - target temperature
    - valve switch

Steps:
  - Fetch config from Redis
  - Fetch data from Redis
  - Check satisfaction
  - Update status
  - hass.service.call to open/close valve for each zone (respect at least one valve has to be open - fallback can be used if necessary)
  - Update data to Redis

## Integration Setup
When creating the integration, there will be inputs for:
  - Redis connection configuration
    - Host, port, credentials, keys prefix (default: empty)
  - Main Climate Entity reference - this will be used as the target entity to read/write its target temperature and read its current temperature
  - Automation Configuration:
    - Main Target When All Zones Satisfied (slider 0-100%) - What to set the main climate target when all zones have reached their targets
      - 0% = Use lowest zone target (energy efficient)
      - 50% = Use average zone target (balanced approach, default)
      - 100% = Use highest zone target (keeps boiler warmer)
    This is used to maintain temperatures in the rooms when all zones are satisfied.
  - Minimum Valves Open: Number of valves to keep open at all times for system safety (default: 1)
  - Main Min/Max Temperature: Temperature range for main climate entity (HVAC unit) (default: 18.0-30.0°C)
  - Main Change Threshold: Minimum temperature change to update main climate (default: 0.5°C)

This should set up the main climate device, which will be monitoring and managing the main climate entity.
Once the integration is created, there is nothing to manage yet except the main climate. We can just see the actual main climate target temperature. User has the option to add a climate zone. This part will create a climate entity for the zone (something like Generic Thermostat in HA).
When there is at least 1 zone turned ON, the multizone feature can be turned on by manual switch.
When the multizone feature is turned on, automations resp. calculations are turned on.

## Add Climate Zone
Inputs:
  - Climate zone name (e.g., Bedroom)
  - Climate zone temperature sensor - temperature sensor entity (that's the temperature sensor in the room)
  - Climate zone valve switch - switch entity (that controls the heat pipe valve to open/close for the room)
  - Climate zone target change threshold - what's the step to change target temperature (Default: 0.1)
  - Climate zone opening offset below target - temperature offset below target to trigger valve opening (default: 0.3°C)
  - Climate closing offset above target - temperature offset above target to trigger valve closing (default: 0.3°C)
These climates should be subdevices of the main device which holds the main climate entity target temperature sensor and core automation as well.
These zone climate entities control target temperature, but they do not control valves.
They only provide information about current temperature, target temperature, and satisfaction status in the zone.

# Algorithms

## Calculate Main Target Temperature

This algorithm determines the target temperature for the main HVAC thermostat based on all zone target temperatures and their current satisfaction states.

### Approach: Slider-Based Mapping (Choice A) or True Average (Choice B)

**Choice A - Slider-Based Linear Interpolation:**

The "Main Target When All Zones Satisfied" slider (0-100%) controls how the main climate target is calculated when all zones are satisfied:

- **0%**: Main target = lowest zone target (energy efficient, minimal heating)
- **50%**: Main target = linear interpolation midpoint (balanced approach)
- **100%**: Main target = highest zone target (keeps boiler warmer, faster response)

**Choice B - True Average:**

Calculate the arithmetic mean of all active zone targets (no slider needed):

- Main target = average of all zone targets
- Example: zones [20°C, 23°C, 24°C] → main target = 22.3°C (rounded to 22.5°C)

**Note:** The implementation should support both approaches as a configuration option.

### Formula

**Choice A - Slider-Based:**
```
slider_position = config.main_target_all_zones_satisfied  // value from 0.0 to 1.0

// Find min and max zone targets (excluding zones turned OFF)
min_zone_target = min(zone.target_temperature for all active zones)
max_zone_target = max(zone.target_temperature for all active zones)

// Linear interpolation based on slider
main_target_raw = min_zone_target + slider_position * (max_zone_target - min_zone_target)

// Round to nearest 0.5°C increment
main_target_rounded = round(main_target_raw * 2) / 2  // e.g., 22.3 → 22.5, 22.2 → 22.0

// Clamp to configured main climate limits
main_target = clamp(main_target_rounded, config.main_min_temp, config.main_max_temp)

// Only update if change exceeds threshold
if abs(main_target - current_main_target) >= config.main_change_threshold:
    update_main_climate_target(main_target)
```

**Choice B - True Average:**
```
// Calculate average of all active zone targets (excluding zones turned OFF and overheated zones)
active_zone_targets = [zone.target_temperature for zone in zones if zone.state == "ON" and zone.satisfaction != "overheated"]
main_target_raw = sum(active_zone_targets) / len(active_zone_targets)

// Round to nearest 0.5°C increment
main_target_rounded = round(main_target_raw * 2) / 2  // e.g., 22.3 → 22.5, 22.2 → 22.0

// Clamp to configured main climate limits
main_target = clamp(main_target_rounded, config.main_min_temp, config.main_max_temp)

// Only update if change exceeds threshold
if abs(main_target - current_main_target) >= config.main_change_threshold:
    update_main_climate_target(main_target)
```

**Note:** User input should include a debounce of ~5 seconds to prevent excessive recalculations during rapid target adjustments.

### Pseudocode

```python
def calculate_main_target_temperature(zones, config, current_main_target):
    """
    Calculate the main HVAC target temperature based on zone targets.
    
    Args:
        zones: List of climate zones with target_temperature
        config: Configuration with main_target_all_zones_satisfied (0.0-1.0) or use_average_mode,
                main_min_temp, main_max_temp, main_change_threshold
        current_main_target: Current main climate target temperature
    
    Returns:
        New main target temperature (or None if no update needed)
    """
    if not zones:
        return None
    
    # Get active zones (turned ON) and exclude overheated zones
    active_zones = [z for z in zones if z.state != "OFF"]
    if not active_zones:
        return None
    
    # Exclude overheated zones from main target calculation
    non_overheated_zones = [z for z in active_zones if z.satisfaction != "overheated"]
    
    if not non_overheated_zones:
        # All zones are overheated - use fallback logic
        zone_targets = [z.target_temperature for z in active_zones]
    else:
        zone_targets = [z.target_temperature for z in non_overheated_zones]
    
    # Calculate main target based on chosen method
    if config.use_average_mode:
        # Choice B: True average
        main_target_raw = sum(zone_targets) / len(zone_targets)
    else:
        # Choice A: Slider-based linear interpolation
        min_target = min(zone_targets)
        max_target = max(zone_targets)
        
        slider = config.main_target_all_zones_satisfied  # 0.0 to 1.0
        if min_target == max_target:
            main_target_raw = min_target
        else:
            main_target_raw = min_target + slider * (max_target - min_target)
    
    # Round to nearest 0.5°C increment
    main_target_rounded = round(main_target_raw * 2) / 2
    
    # Clamp to configured limits
    main_target = max(config.main_min_temp, 
                      min(config.main_max_temp, main_target_rounded))
    
    # Only update if change is significant
    if abs(main_target - current_main_target) >= config.main_change_threshold:
        return main_target
    
    return None
```

### Numeric Example

**Configuration:**
- `main_target_all_zones_satisfied` = 0.5 (50%, average)
- `main_min_temp` = 18.0°C
- `main_max_temp` = 30.0°C
- `main_change_threshold` = 0.5°C

**Zones:**
- Bedroom: target = 20.0°C
- Living Room: target = 22.0°C
- Kitchen: target = 19.0°C
- Bathroom: target = 23.0°C

**Calculation:**
```
min_target = 19.0°C
max_target = 23.0°C
slider = 0.5

main_target_raw = 19.0 + 0.5 * (23.0 - 19.0)
                = 19.0 + 0.5 * 4.0
                = 19.0 + 2.0
                = 21.0°C

main_target = clamp(21.0, 18.0, 30.0) = 21.0°C
```

**Result:** Main climate target set to **21.0°C**

**Different slider values:**
- Slider at 0% (0.0): main_target = 19.0°C (lowest zone)
- Slider at 25% (0.25): main_target = 20.0°C
- Slider at 50% (0.5): main_target = 21.0°C (linear midpoint)
- Slider at 75% (0.75): main_target = 22.0°C
- Slider at 100% (1.0): main_target = 23.0°C (highest zone)

**Using average mode (Choice B):**
- Average = (19 + 20 + 22 + 23) / 4 = 21.0°C
- With rounding: 21.0°C (already at 0.5 increment)

**Note:** For zones [20°C, 23°C, 24°C], average = 22.333°C → rounded to 22.5°C

---

## Update Valves Algorithm

This algorithm manages the opening and closing of zone valves based on current and target temperatures, ensuring system safety and preventing rapid valve cycling (chattering).

### Core Behavior

1. **Determine zone satisfaction state** for each zone
2. **Sort zones by priority** (those needing heat most urgently)
3. **Apply safety rules** (minimum valves open)
4. **Execute valve changes** using open-first-then-close sequence
5. **Record valve locks** to prevent immediate re-actuation

### Zone Satisfaction States

Each zone is classified based on its current temperature relative to target. The satisfaction state is different from valve control logic - valves still open/close based on opening_offset and closing_offset, but the zone's satisfaction status is determined by proximity to the target temperature.

**Heating Mode:**
- **Underheated**: `current_temp < (target_temp - opening_offset)` → Valve opens
  - **Becomes satisfied when**: `current_temp >= (target_temp - satisfaction_eps)` (zone has reached target while rising)
- **Satisfied**: `(target_temp - satisfaction_eps) <= current_temp <= (target_temp + satisfaction_eps)` → Maintains temperature
  - Valve may still be open or closed depending on opening_offset and closing_offset
- **Overheated**: `current_temp > (target_temp + closing_offset)` → Valve closes
  - **Becomes satisfied when**: `current_temp <= (target_temp + satisfaction_eps)` (zone has reached target while falling)

**Cooling Mode** (inverted logic):
- **Undercooled**: `current_temp > (target_temp + opening_offset)` → Valve opens
  - **Becomes satisfied when**: `current_temp <= (target_temp + satisfaction_eps)` (zone has reached target while falling)
- **Satisfied**: `(target_temp - satisfaction_eps) <= current_temp <= (target_temp + satisfaction_eps)` → Maintains temperature
  - Valve may still be open or closed depending on opening_offset and closing_offset
- **Overcooled**: `current_temp < (target_temp - closing_offset)` → Valve closes
  - **Becomes satisfied when**: `current_temp >= (target_temp - satisfaction_eps)` (zone has reached target while rising)

**Key Distinction:**
- **Valve control** (opening/closing): Still uses `opening_offset` and `closing_offset` for hysteresis
- **Satisfaction status**: Uses `satisfaction_eps` centered around target temperature
- **satisfaction_eps** parameter (default: 0.0):
  - 0.0 = Zone is satisfied only when exactly at target temperature
  - 0.1 = Zone is satisfied when within ±0.1°C of target temperature
  - Provides a buffer zone around the target for satisfaction determination

**Example (Heating Mode):**
- Target: 21.0°C, opening_offset: 0.3°C, closing_offset: 0.3°C, satisfaction_eps: 0.1°C
- Underheated zone (currently 20.5°C): Valve opens at 20.7°C, but zone becomes "satisfied" at 20.9°C (21.0 - 0.1)
- Overheated zone (currently 21.5°C): Valve closes at 21.3°C, but zone becomes "satisfied" at 21.1°C (21.0 + 0.1)

### Priority Sorting

Zones are sorted for valve management using a two-tier priority system:

1. **Primary sorting**: By user-defined priority value (higher number = higher priority)
2. **Secondary sorting**: By temperature deficit when priorities are equal

**Heating mode:**
```python
# Primary sort by priority (higher first)
# Secondary sort by deficit (higher deficit = more urgent)
deficit = target_temp - current_temp

if zone.priority > 0:
    sort_key = (zone.priority, deficit)  # Explicit priority takes precedence
else:
    sort_key = (0, deficit)  # Default: sort by temperature deficit only
```

**Cooling mode:**
```python
deficit = current_temp - target_temp
sort_key = (zone.priority, deficit)  # Same logic as heating
```

**Example:**
- Zone A: priority=10, deficit=2.0°C → sort_key=(10, 2.0)
- Zone B: priority=5, deficit=3.0°C → sort_key=(5, 3.0)
- Zone C: priority=0, deficit=4.0°C → sort_key=(0, 4.0)
- Zone D: priority=0, deficit=1.0°C → sort_key=(0, 1.0)

**Sort order:** A → B → C → D (A managed first, D managed last)

### Safety Rules

1. **Minimum valves open**: At least `config.min_valves_open` valves must remain open at all times
2. **Fallback valves**: If insufficient valves would be open, force open fallback valves
3. **Open-first-then-close**: When at minimum valves open and need to swap, open the new valve first, wait for `valve_actuation_delay`, then close the old valve. Otherwise, valves can open and close simultaneously.

### Open-First-Then-Close Sequence

To maintain minimum flow through the HVAC system:

1. Identify valves to open and valves to close
2. **If currently at minimum valves open and need to swap:**
   - Open the new valve(s) first
   - Set valve lock: `valve_lock[valve_id] = now + valve_actuation_delay`
   - Wait for physical valve to fully open
   - Then close the old valve(s)
3. **Otherwise:**
   - Valves can open and close simultaneously (no wait required)

### Valve Locks and Cooldown

To prevent chattering (rapid open/close cycles):

- **Valve lock**: After actuating a valve, record `valve_lock[valve_id] = timestamp + cooldown`
- **Cooldown period**: `valve_actuation_delay` (e.g., 120 seconds)
- **Skip locked valves**: Don't actuate a valve again until its lock expires

**Redis key pattern:**
```
ha_multizone:valvelock:{valve_id} = {"locked_until": "2026-01-13T14:30:00Z"}
```

### Edge Cases

1. **All zones satisfied**: Open valves for all satisfied zones (excluding disabled/OFF zones). If a zone was previously overheated and its valve was closed, it should now be opened to maintain stable temperatures at the configured main target.
2. **All zones overheated**: Close all except minimum required valves, prioritizing fallback valves. Overheated zones are excluded from main target temperature calculation.
3. **Multizone feature OFF**: Each zone manages its own valve automatically - underheated zones open their valves, overheated zones close their valves. Safety check still runs to ensure minimum valves open.
4. **Zone turned OFF**: Close its valve (unless it's a required fallback)

### Pseudocode

```python
def update_valves(zones, config, main_climate_state, multizone_enabled):
    """
    Update valve states based on zone temperatures and satisfaction.
    
    Args:
        zones: List of climate zones with current_temp, target_temp, valve_id, state
        config: Configuration with min_valves_open, valve_actuation_delay, opening_offset, closing_offset
        main_climate_state: Main HVAC state (HEATING, COOLING, OFF)
        multizone_enabled: Whether multizone feature is active
    
    Returns:
        List of valve actions to execute
    """
    if not multizone_enabled:
        # Multizone feature OFF - each zone manages its own valve
        # Underheated zones open valves, overheated zones close valves
        # Safety check still ensures minimum valves open
        actions = []
        
        for zone in zones:
            if zone.state == "OFF":
                continue
            
            # Determine satisfaction (same logic as when multizone is on)
            if main_climate_state == "HEATING":
                if zone.current_temp < (zone.target_temp - config.opening_offset):
                    actions.append({"valve_id": zone.valve_id, "action": "open"})
                elif zone.current_temp > (zone.target_temp + config.closing_offset):
                    actions.append({"valve_id": zone.valve_id, "action": "close"})
            else:  # COOLING
                if zone.current_temp > (zone.target_temp + config.opening_offset):
                    actions.append({"valve_id": zone.valve_id, "action": "open"})
                elif zone.current_temp < (zone.target_temp - config.closing_offset):
                    actions.append({"valve_id": zone.valve_id, "action": "close"})
        
        return actions
    
    # Determine satisfaction state for each zone
    # Note: Satisfaction uses satisfaction_eps (centered around target)
    # Valve opening/closing still uses opening_offset and closing_offset
    for zone in zones:
        if zone.state == "OFF":
            zone.satisfaction = "off"
            continue
        
        if main_climate_state == "HEATING":
            # Valve control logic (unchanged)
            if zone.current_temp < (zone.target_temp - config.opening_offset):
                # Zone is underheated, valve should be open
                # But satisfaction depends on proximity to target
                if zone.current_temp >= (zone.target_temp - config.satisfaction_eps):
                    zone.satisfaction = "satisfied"  # Reached target while rising
                else:
                    zone.satisfaction = "underheated"
            elif zone.current_temp > (zone.target_temp + config.closing_offset):
                # Zone is overheated, valve should be closed
                # But satisfaction depends on proximity to target
                if zone.current_temp <= (zone.target_temp + config.satisfaction_eps):
                    zone.satisfaction = "satisfied"  # Reached target while falling
                else:
                    zone.satisfaction = "overheated"
            else:
                # Zone is in the hysteresis band - check satisfaction around target
                if (zone.target_temp - config.satisfaction_eps) <= zone.current_temp <= (zone.target_temp + config.satisfaction_eps):
                    zone.satisfaction = "satisfied"
                elif zone.current_temp < zone.target_temp:
                    zone.satisfaction = "underheated"
                else:
                    zone.satisfaction = "overheated"
        else:  # COOLING
            # Valve control logic (unchanged)
            if zone.current_temp > (zone.target_temp + config.opening_offset):
                # Zone is undercooled, valve should be open
                # But satisfaction depends on proximity to target
                if zone.current_temp <= (zone.target_temp + config.satisfaction_eps):
                    zone.satisfaction = "satisfied"  # Reached target while falling
                else:
                    zone.satisfaction = "undercooled"
            elif zone.current_temp < (zone.target_temp - config.closing_offset):
                # Zone is overcooled, valve should be closed
                # But satisfaction depends on proximity to target
                if zone.current_temp >= (zone.target_temp - config.satisfaction_eps):
                    zone.satisfaction = "satisfied"  # Reached target while rising
                else:
                    zone.satisfaction = "overcooled"
            else:
                # Zone is in the hysteresis band - check satisfaction around target
                if (zone.target_temp - config.satisfaction_eps) <= zone.current_temp <= (zone.target_temp + config.satisfaction_eps):
                    zone.satisfaction = "satisfied"
                elif zone.current_temp > zone.target_temp:
                    zone.satisfaction = "undercooled"
                else:
                    zone.satisfaction = "overcooled"
    
    # Calculate sort key (user priority + temperature deficit)
    for zone in zones:
        if zone.state == "OFF":
            zone.sort_key = (-1000, -1000)  # Lowest priority
        elif main_climate_state == "HEATING":
            deficit = zone.target_temp - zone.current_temp
            zone.sort_key = (zone.priority, deficit)
        else:  # COOLING
            deficit = zone.current_temp - zone.target_temp
            zone.sort_key = (zone.priority, deficit)
    
    # Sort zones by priority (user priority first, then deficit)
    sorted_zones = sorted(zones, key=lambda z: z.sort_key, reverse=True)
    
    # Determine desired valve states
    valves_to_open = []
    valves_to_close = []
    
    for zone in sorted_zones:
        if zone.state == "OFF":
            valves_to_close.append(zone.valve_id)
        elif main_climate_state == "HEATING":
            if zone.satisfaction == "underheated":
                valves_to_open.append(zone.valve_id)
            elif zone.satisfaction == "overheated":
                valves_to_close.append(zone.valve_id)
            elif zone.satisfaction == "satisfied":
                # Satisfied zones should have valves open to maintain temperature
                valves_to_open.append(zone.valve_id)
        else:  # COOLING
            if zone.satisfaction == "undercooled":
                valves_to_open.append(zone.valve_id)
            elif zone.satisfaction == "overcooled":
                valves_to_close.append(zone.valve_id)
            elif zone.satisfaction == "satisfied":
                # Satisfied zones should have valves open to maintain temperature
                valves_to_open.append(zone.valve_id)
    
    # Apply safety: ensure minimum valves open
    currently_open = get_currently_open_valves(zones)
    will_be_open = (currently_open - set(valves_to_close)) | set(valves_to_open)
    
    if len(will_be_open) < config.min_valves_open:
        # Force open fallback valves
        shortage = config.min_valves_open - len(will_be_open)
        fallback_candidates = get_fallback_valves(zones, exclude=will_be_open)
        for valve_id in fallback_candidates[:shortage]:
            valves_to_open.append(valve_id)
            if valve_id in valves_to_close:
                valves_to_close.remove(valve_id)
    
    # Check valve locks (cooldown)
    now = get_current_time()
    valves_to_open = [v for v in valves_to_open if not is_valve_locked(v, now)]
    valves_to_close = [v for v in valves_to_close if not is_valve_locked(v, now)]
    
    # Execute with open-first-then-close logic (only when at minimum valves)
    actions = []
    
    # If at minimum and swapping, open first and wait
    if len(currently_open) == config.min_valves_open and valves_to_open and valves_to_close:
        # Open new valves first
        for valve_id in valves_to_open:
            actions.append({
                "valve_id": valve_id,
                "action": "open",
                "timestamp": now
            })
            set_valve_lock(valve_id, now + config.valve_actuation_delay)
        
        # Schedule closing of old valves after delay
        for valve_id in valves_to_close:
            actions.append({
                "valve_id": valve_id,
                "action": "close",
                "delay": config.valve_actuation_delay,
                "timestamp": now + config.valve_actuation_delay
            })
            set_valve_lock(valve_id, now + config.valve_actuation_delay)
    else:
        # Normal operation: valves can open and close simultaneously
        for valve_id in valves_to_close:
            actions.append({
                "valve_id": valve_id,
                "action": "close",
                "timestamp": now
            })
            set_valve_lock(valve_id, now + config.valve_actuation_delay)
        
        for valve_id in valves_to_open:
            actions.append({
                "valve_id": valve_id,
                "action": "open",
                "timestamp": now
            })
            set_valve_lock(valve_id, now + config.valve_actuation_delay)
    
    return actions
```

### Example Walkthrough: Open-First-Then-Close with Valve Actuation Delay

**Initial State:**
- Minimum valves open: 1
- Currently open: Bedroom valve
- valve_actuation_delay: 120 seconds

**Scenario:** Bedroom is now satisfied, but Kitchen needs heat

**Step-by-step:**

1. **T=0s**: Algorithm runs
   - Bedroom: satisfied (should close)
   - Kitchen: underheated (should open)
   - Currently 1 valve open (at minimum)
   
2. **T=0s**: Open Kitchen valve FIRST
   ```
   Action: OPEN Kitchen valve
   Set valve_lock[Kitchen] = T+120s
   ```
   
3. **T=0s to T=120s**: Both valves open (exceeds minimum, but safe)
   - Physical Kitchen valve opening...
   
4. **T=120s**: Close Bedroom valve
   ```
   Action: CLOSE Bedroom valve
   Set valve_lock[Bedroom] = T+240s
   ```
   
5. **T=120s+**: System stable
   - Kitchen valve open (minimum maintained)

**Result:** Minimum flow maintained throughout the transition.

---

## Safety Valve Check Algorithm
- Checks if the minimum required number of valves are open
- If not, log a warning and open fallback valves.

### Pseudocode

```python
def safety_valve_check(zones, config):
    """
    Ensure minimum number of valves are open for system safety.
    
    Args:
        zones: List of climate zones with valve states
        config: Configuration with min_valves_open
    
    Returns:
        List of fallback valves to force open (if needed)
    """
    currently_open = [z for z in zones if z.valve_state == "open"]
    
    if len(currently_open) < config.min_valves_open:
        shortage = config.min_valves_open - len(currently_open)
        log_warning(f"Safety check: Only {len(currently_open)} valves open, need {config.min_valves_open}")
        
        # Get fallback valves
        fallback_valves = get_fallback_valves(zones, exclude=currently_open)
        valves_to_force_open = fallback_valves[:shortage]
        
        for valve in valves_to_force_open:
            log_warning(f"Safety: Force opening fallback valve {valve.id}")
        
        return valves_to_force_open
    
    return []
```

---

## Background Jobs and Process Locking

- Process locker (redis can be used)
  - At the same time there can be only one running job per type
    - Update valves
    - Calculate main target temperature
    - Safety valve check
- Managing background jobs using queues
  - 2 FIFO queues - one for Update valves and one for Calculate main target temperature

### Job Lock Pattern (Redis)

```python
def acquire_job_lock(job_type, timeout=60):
    """
    Acquire a lock for a specific job type.
    
    Args:
        job_type: "update_valves", "calculate_main_temp", or "safety_check"
        timeout: Lock timeout in seconds
    
    Returns:
        True if lock acquired, False otherwise
    """
    lock_key = f"ha_multizone:joblock:{job_type}"
    now = time.time()
    
    # Try to set lock with expiration
    success = redis.set(lock_key, now, nx=True, ex=timeout)
    return success

def release_job_lock(job_type):
    """Release the job lock."""
    lock_key = f"ha_multizone:joblock:{job_type}"
    redis.delete(lock_key)
```

# Redis Schema

Redis is used to store configuration, zone states, job queues, and synchronization locks. All keys use a configurable prefix (default: `ha_multizone`).

## Key Patterns

### Global Configuration
```
Key: ha_multizone:config
Type: Hash
Description: Stores global configuration parameters
```

**Example JSON:**
```json
{
  "main_target_all_zones_satisfied": 0.5,
  "use_average_mode": false,
  "min_valves_open": 1,
  "main_min_temp": 18.0,
  "main_max_temp": 30.0,
  "main_change_threshold": 0.5,
  "valve_actuation_delay": 120,
  "command_cooldown": 60,
  "coordinator_interval": 15,
  "job_status_ttl": 900,
  "satisfaction_eps": 0.0
}
```

### Zone Configuration
```
Key: ha_multizone:zones
Type: List
Description: List of all zone IDs
```

**Example:**
```json
["zone_bedroom", "zone_living_room", "zone_kitchen", "zone_bathroom"]
```

### Per-Zone State
```
Key: ha_multizone:zone:{zone_id}
Type: Hash
Description: Stores state and configuration for a specific zone
```

**Example JSON:**
```json
{
  "id": "zone_bedroom",
  "name": "Bedroom",
  "temperature_sensor_entity_id": "sensor.bedroom_temperature",
  "valve_switch_entity_id": "switch.bedroom_valve",
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "state": "ON",
  "satisfaction": "underheated",
  "valve_state": "open",
  "target_change_threshold": 0.1,
  "opening_offset": 0.3,
  "closing_offset": 0.3,
  "is_fallback_valve": false,
  "priority": 0,
  "last_updated": "2026-01-13T13:30:00Z"
}
```

### Main Climate State
```
Key: ha_multizone:main_climate
Type: Hash
Description: Stores main HVAC climate entity state
```

**Example JSON:**
```json
{
  "entity_id": "climate.main_thermostat",
  "current_temperature": 20.8,
  "target_temperature": 21.0,
  "outdoor_temperature": 5.0,
  "hvac_mode": "MANUAL",
  "hvac_action": "HEATING",
  "multizone_enabled": true,
  "last_updated": "2026-01-13T13:30:00Z"
}
```

### Job Queues
```
Key: ha_multizone:queue:update_valves
Type: List (FIFO)
Description: Queue of pending "update valves" jobs

Key: ha_multizone:queue:calculate_main_temp
Type: List (FIFO)
Description: Queue of pending "calculate main temp" jobs
```

**Example Queue Entry:**
```json
{
  "job_id": "calc_temp_20260113_133000_001",
  "job_type": "calculate_main_temp",
  "enqueued_at": "2026-01-13T13:30:00Z",
  "parameters": {
    "trigger": "zone_bedroom_target_changed",
    "changed_zones": ["zone_bedroom"]
  }
}
```

### Valve Locks
```
Key: ha_multizone:valvelock:{valve_id}
Type: String (timestamp)
Description: Lock timestamp preventing valve re-actuation until cooldown expires
TTL: Set to valve_actuation_delay
```

**Example:**
```json
{
  "valve_id": "switch.bedroom_valve",
  "locked_until": "2026-01-13T13:32:00Z",
  "reason": "opened_at_13:30:00"
}
```

### Job Locks
```
Key: ha_multizone:joblock:{job_type}
Type: String (timestamp)
Description: Prevents concurrent execution of same job type
TTL: Set to 60 seconds (auto-release if job crashes)
```

**Example:**
```json
{
  "job_type": "update_valves",
  "acquired_at": "2026-01-13T13:30:00Z",
  "acquired_by": "worker_thread_1"
}
```

### Job Status
```
Key: ha_multizone:jobstatus:{job_id}
Type: Hash
Description: Tracks execution status of background jobs
TTL: Configurable (default: 900 seconds / 15 minutes after completion)
```

**Example JSON:**
```json
{
  "job_id": "update_valves_20260113_133000_001",
  "job_type": "update_valves",
  "status": "completed",
  "started_at": "2026-01-13T13:30:00Z",
  "completed_at": "2026-01-13T13:30:02Z",
  "duration_ms": 2341,
  "actions_taken": 3,
  "errors": [],
  "result": {
    "valves_opened": ["switch.kitchen_valve"],
    "valves_closed": ["switch.bedroom_valve"],
    "valves_unchanged": ["switch.living_room_valve"]
  }
}
```

## Redis Data Flow

1. **Configuration changes** → Update `ha_multizone:config`
2. **Zone state changes** → Update `ha_multizone:zone:{zone_id}`
3. **Temperature/target changes** → Enqueue job to `ha_multizone:queue:calculate_main_temp`
4. **Coordinator** → Dequeue jobs from queues, acquire job locks, execute
5. **Valve actuation** → Set `ha_multizone:valvelock:{valve_id}` with TTL
6. **Job completion** → Update `ha_multizone:jobstatus:{job_id}`, release job lock

---

# Configuration Examples

This section maps the UI configuration fields to their JSON storage format and provides recommended default values.

## Integration Setup Configuration

### Redis Connection
**UI Fields:**
- Host: `localhost`
- Port: `6379`
- Password: (optional, empty by default)
- Database: `0`
- Key Prefix: (optional, default: `ha_multizone`)

**Stored in Home Assistant config entry** (not Redis):
```json
{
  "redis": {
    "host": "localhost",
    "port": 6379,
    "password": null,
    "db": 0,
    "key_prefix": "ha_multizone"
  }
}
```

### Main Climate Configuration
**UI Fields:**
- Main Climate Entity: `climate.main_thermostat` (entity selector)

**Stored in `ha_multizone:config`:**
```json
{
  "main_climate_entity_id": "climate.main_thermostat"
}
```

### Automation Configuration
**UI Fields:**
- Main Target Calculation Mode: Choice (default: "Slider-based")
  - Slider-based: Use linear interpolation with slider
  - Average: Use arithmetic mean of all zone targets
- Main Target When All Zones Satisfied: Slider 0-100% (default: 50%, only visible when Slider-based mode selected)
- Minimum Valves Open: Number (default: 1)
- Main Min Temperature: Number °C (default: 18.0)
- Main Max Temperature: Number °C (default: 30.0)
- Main Change Threshold: Number °C (default: 0.5)
- Valve Actuation Delay: Number seconds (default: 120)
- Coordinator Interval: Number seconds (default: 15)
- Job Status TTL: Number seconds (default: 900 / 15 minutes)
- Satisfaction Epsilon: Number °C (default: 0.0)
  - Buffer zone around target temperature for satisfaction determination
  - 0.0 = Zone is satisfied only at exact target temperature
  - 0.1 = Zone is satisfied within ±0.1°C of target

**Stored in `ha_multizone:config`:**
```json
{
  "main_target_all_zones_satisfied": 0.5,
  "use_average_mode": false,
  "min_valves_open": 1,
  "main_min_temp": 18.0,
  "main_max_temp": 30.0,
  "main_change_threshold": 0.5,
  "valve_actuation_delay": 120,
  "command_cooldown": 60,
  "coordinator_interval": 15,
  "job_status_ttl": 900,
  "satisfaction_eps": 0.0
}
```

## Zone Configuration

### Add Climate Zone
**UI Fields:**
- Zone Name: Text (e.g., "Bedroom")
- Temperature Sensor: Entity selector (e.g., `sensor.bedroom_temperature`)
- Valve Switch: Entity selector (e.g., `switch.bedroom_valve`)
- Target Change Threshold: Number °C (default: 0.1)
- Opening Offset Below Target: Number °C (default: 0.3)
- Closing Offset Above Target: Number °C (default: 0.3)
- Is Fallback Valve: Boolean (default: false) - Force this valve to stay open when minimum valves requirement applies
- Priority: Number (default: 0) - Higher values are managed first; if all zones have priority 0, zones are prioritized by temperature deficit (most urgent need)

**Stored in `ha_multizone:zone:{zone_id}`:**
```json
{
  "id": "zone_bedroom",
  "name": "Bedroom",
  "temperature_sensor_entity_id": "sensor.bedroom_temperature",
  "valve_switch_entity_id": "switch.bedroom_valve",
  "target_change_threshold": 0.1,
  "opening_offset": 0.3,
  "closing_offset": 0.3,
  "is_fallback_valve": false,
  "priority": 0,
  "current_temperature": null,
  "target_temperature": 20.0,
  "state": "OFF",
  "satisfaction": "unknown",
  "valve_state": "closed"
}
```

## Complete Configuration Example

**Full `ha_multizone:config`:**
```json
{
  "main_climate_entity_id": "climate.main_thermostat",
  "main_target_all_zones_satisfied": 0.5,
  "use_average_mode": false,
  "min_valves_open": 1,
  "main_min_temp": 18.0,
  "main_max_temp": 30.0,
  "main_change_threshold": 0.5,
  "valve_actuation_delay": 120,
  "command_cooldown": 60,
  "coordinator_interval": 15,
  "job_status_ttl": 900,
  "satisfaction_eps": 0.0,
  "multizone_enabled": false,
  "created_at": "2026-01-13T10:00:00Z",
  "updated_at": "2026-01-13T13:00:00Z"
}
```

**All zones in `ha_multizone:zones`:**
```json
["zone_bedroom", "zone_living_room", "zone_kitchen", "zone_bathroom"]
```

**Example zone data `ha_multizone:zone:zone_bedroom`:**
```json
{
  "id": "zone_bedroom",
  "name": "Bedroom",
  "temperature_sensor_entity_id": "sensor.bedroom_temperature",
  "valve_switch_entity_id": "switch.bedroom_valve",
  "current_temperature": 20.5,
  "target_temperature": 21.0,
  "state": "ON",
  "satisfaction": "underheated",
  "valve_state": "open",
  "target_change_threshold": 0.1,
  "opening_offset": 0.3,
  "closing_offset": 0.3,
  "is_fallback_valve": true,
  "priority": 10,
  "last_updated": "2026-01-13T13:30:00Z"
}
```

---

# Timing, Delays and Actuation

This section describes the timing parameters that control when and how the multizone system responds to temperature changes.

## Key Timing Parameters

### Valve Actuation Delay
**Parameter:** `valve_actuation_delay`  
**Default:** 120 seconds (2 minutes)  
**Purpose:** Physical time required for a valve to fully open or close

**Rationale:**
- Motorized ball valves typically take 60-180 seconds to complete a full rotation
- This delay ensures a valve is fully actuated before allowing another change
- Used to set valve lock duration (cooldown period)
- Critical for open-first-then-close sequence to maintain minimum flow

**Usage:**
- After opening/closing a valve, set `valve_lock` for this duration
- When swapping valves at minimum: open new valve, wait this delay, then close old valve
- Prevents chattering (rapid open/close cycles)

### Command Cooldown
**Parameter:** `command_cooldown`  
**Default:** 60 seconds (1 minute)  
**Purpose:** Minimum time between consecutive commands to same entity

**Rationale:**
- Prevents overwhelming the HVAC system or valve controllers
- Gives time for temperature changes to propagate
- Reduces wear on mechanical components

### Coordinator Interval
**Parameter:** `coordinator_interval`  
**Default:** 15 seconds  
**Purpose:** How often the coordinator checks for pending jobs and updates sensor states

**Rationale:**
- Frequent enough to be responsive (temperature changes detected within 15s)
- Infrequent enough to minimize CPU/Redis load
- Balances responsiveness with system efficiency

### Main Change Threshold
**Parameter:** `main_change_threshold`  
**Default:** 0.5°C  
**Purpose:** Minimum temperature change required to update main climate target

**Rationale:**
- Prevents excessive updates to main thermostat for tiny changes
- Most thermostats have 0.5°C precision
- Reduces API calls to cloud-connected thermostats
- Target temperature is rounded to nearest 0.5°C increment (e.g., 22.3°C → 22.5°C, 22.2°C → 22.0°C)
- With rounding to 0.5°C increments, the threshold check is technically redundant (changes will always be in 0.5°C steps), but kept for explicitness and future flexibility

**Note:** User input changes should be debounced by ~5 seconds to prevent excessive recalculations during rapid adjustments.

### Zone Opening/Closing Offsets
**Parameter:** `opening_offset`, `closing_offset`  
**Default:** 0.3°C  
**Purpose:** Hysteresis band around target temperature

**Rationale:**
- Prevents valve cycling when temperature hovers near target
- Creates a "satisfied" band: `[target - opening_offset, target + closing_offset]`
- Example: target 21°C, offsets 0.3°C → satisfied when temp is 20.7-21.3°C

## Timing Sequences

### Scenario 1: Zone Temperature Drop

```
T=0s:     Bedroom temp drops to 20.4°C (target: 21.0°C, opening_offset: 0.3°C)
          → Underheated (20.4 < 20.7)
T=0s:     Temperature change detected
T=0s:     "Update main target temp" job enqueued
T=0s:     "Update valves" job enqueued
T=0-15s:  Jobs wait in queue
T=15s:    Coordinator runs
T=15s:    Dequeue "Calculate main temp" job → Execute
T=15s:    Calculate new main target, update main climate entity
T=15s:    Dequeue "Update valves" job → Execute
T=15s:    Open Bedroom valve
T=15s:    Set valve_lock[Bedroom] until T=135s
T=15-135s: Valve opening (physical actuation)
T=135s:   Valve fully open, lock expires
```

### Scenario 2: Swapping Valves at Minimum

```
Initial:  Living Room valve OPEN (only valve open, minimum=1)
T=0s:     Living Room reaches target (satisfied)
T=0s:     Kitchen needs heat (underheated)
T=0s:     "Update valves" job enqueued
T=15s:    Coordinator runs, executes "Update valves" job
T=15s:    Detect: at minimum (1 valve open), need to swap
T=15s:    Open Kitchen valve FIRST
T=15s:    Set valve_lock[Kitchen] until T=135s
T=15-135s: Kitchen valve opening (both valves now open)
T=135s:   Close Living Room valve (now safe, Kitchen is open)
T=135s:   Set valve_lock[LivingRoom] until T=255s
T=135-255s: Living Room valve closing
T=255s:   System stable, Kitchen valve open
```

### Scenario 3: Safety Check Interval

```
Safety check automation runs every: valve_actuation_delay / 2
With valve_actuation_delay=120s → Safety check every 60s

T=0s:     Safety check runs
T=0s:     Check: currently 1 valve open (minimum=1) ✓
T=60s:    Safety check runs again
T=60s:    Check: currently 0 valves open (minimum=1) ✗
T=60s:    WARNING: Force open fallback valve
T=60s:    Open fallback Bedroom valve
```

## Recommended Timing Configurations

### Conservative (Safe, Slower Response)
```json
{
  "valve_actuation_delay": 180,
  "command_cooldown": 90,
  "coordinator_interval": 30,
  "main_change_threshold": 0.5,
  "opening_offset": 0.5,
  "closing_offset": 0.5,
  "satisfaction_eps": 0.2
}
```

### Balanced (Default)
```json
{
  "valve_actuation_delay": 120,
  "command_cooldown": 60,
  "coordinator_interval": 15,
  "main_change_threshold": 0.5,
  "opening_offset": 0.3,
  "closing_offset": 0.3,
  "satisfaction_eps": 0.0
}
```

### Aggressive (Fast Response, More Wear)
```json
{
  "valve_actuation_delay": 60,
  "command_cooldown": 30,
  "coordinator_interval": 10,
  "main_change_threshold": 0.3,
  "opening_offset": 0.2,
  "closing_offset": 0.2,
  "satisfaction_eps": 0.0
}
```

**Note:** Aggressive settings may cause more valve wear and potential chattering. Use conservative or balanced settings for production.

---

# Tests and Scenarios

This section describes concrete test cases to validate the multizone climate system behavior.

## Unit Tests

### Test 1: Calculate Main Temperature - Slider Mapping and Average Mode

**Purpose:** Verify both calculation methods work correctly

**Setup:**
- Zones: Bedroom (20°C), Living Room (22°C), Kitchen (19°C), Bathroom (23°C)
- Config: main_min_temp=18°C, main_max_temp=30°C, main_change_threshold=0.5°C

**Test Cases - Choice A (Slider-based):**

| Slider   | Expected Main Target | Calculation                    |
|----------|----------------------|--------------------------------|
| 0% (0.0) | 19.0°C               | min(19,20,22,23) = 19°C        |
| 25% (0.25) | 20.0°C             | 19 + 0.25*(23-19) = 20°C       |
| 50% (0.5) | 21.0°C              | 19 + 0.5*(23-19) = 21°C        |
| 75% (0.75) | 22.0°C             | 19 + 0.75*(23-19) = 22°C       |
| 100% (1.0) | 23.0°C             | max(19,20,22,23) = 23°C        |

**Test Cases - Choice B (Average mode):**

| Zones                    | Raw Average | Rounded | Expected |
|--------------------------|-------------|---------|----------|
| [19, 20, 22, 23]         | 21.0°C      | 21.0°C  | 21.0°C   |
| [20, 23, 24]             | 22.33°C     | 22.5°C  | 22.5°C   |
| [18.5, 21.2, 22.8]       | 20.83°C     | 21.0°C  | 21.0°C   |

**Expected Behavior:**
- Main target calculated correctly for each method
- Temperatures rounded to nearest 0.5°C increment
- Main climate entity updated when change ≥ 0.5°C
- Main climate entity NOT updated when change < 0.5°C
- Overheated zones excluded from calculation

---

### Test 2: Update Valves - Basic Satisfaction States

**Purpose:** Verify zones correctly classified with new satisfaction logic that uses satisfaction_eps

**Setup (Heating Mode):**
- opening_offset = 0.3°C
- closing_offset = 0.3°C
- satisfaction_eps = 0.1°C

**Test Cases:**

| Zone       | Target | Current | Valve Trigger | Satisfaction Status | Reasoning |
|------------|--------|---------|---------------|---------------------|-----------|
| Bedroom    | 21.0°C | 20.0°C  | OPEN (< 20.7) | Underheated         | 20.0 < 20.9 (target - eps) |
| Living     | 22.0°C | 21.9°C  | No change     | Satisfied           | 21.9 >= 21.9 (target - eps) |
| Kitchen    | 20.0°C | 20.5°C  | CLOSE (> 20.3) | Overheated         | 20.5 > 20.1 (target + eps) |
| Bathroom   | 23.0°C | 24.0°C  | CLOSE (> 23.3) | Overheated         | 24.0 > 23.1 (target + eps) |
| Study      | 21.0°C | 20.95°C | No change     | Satisfied           | 20.95 >= 20.9 (target - eps), zone rising to target |
| Office     | 21.0°C | 21.05°C | No change     | Satisfied           | 21.05 <= 21.1 (target + eps), zone falling to target |

**Key Differences with New Logic:**
- **Valve control** (when to open/close): Uses opening_offset (0.3°C) and closing_offset (0.3°C)
  - Open when: current < (target - 0.3) = 20.7°C for 21°C target
  - Close when: current > (target + 0.3) = 21.3°C for 21°C target
- **Satisfaction determination**: Uses satisfaction_eps (0.1°C) around target
  - Satisfied when: (target - 0.1) <= current <= (target + 0.1)
  - For 21°C target: satisfied when 20.9°C to 21.1°C

**Expected Behavior:**
- Bedroom valve opens (underheated, needs heat)
- Living Room: satisfied status (reached target while rising), valve maintains state
- Kitchen valve closes (overheated, too hot)
- Bathroom valve closes (overheated, too hot)
- Study: satisfied status even though valve might still be open (rising toward target)
- Office: satisfied status even though valve might be closed (falling toward target)
- Overheated zones (Kitchen, Bathroom) excluded from main target calculation

**Comparison with Old Logic:**
- **Old**: Zone was satisfied when in the range [target - opening_offset, target + closing_offset] = [20.7, 21.3]
- **New**: Zone is satisfied when in the range [target - satisfaction_eps, target + satisfaction_eps] = [20.9, 21.1]
- This tighter satisfaction band around the actual target provides better feedback on zone status

---

### Test 3: Safety Fallback - Minimum Valves

**Purpose:** Verify system maintains minimum valves open

**Setup:**
- min_valves_open = 2
- All zones satisfied or overheated (would close all valves)
- Fallback valves: Bedroom (is_fallback_valve=true), Kitchen (is_fallback_valve=true)

**Expected Behavior:**
1. Calculate desired state: all valves would close (all satisfied/overheated)
2. Safety check: 0 < 2 → violation
3. Force open 2 fallback valves: Bedroom, Kitchen
4. Final state: Bedroom OPEN, Kitchen OPEN, others CLOSED

**Test Assertion:**
```python
assert len(open_valves) >= config.min_valves_open
assert "bedroom_valve" in open_valves  # is_fallback_valve = true
assert "kitchen_valve" in open_valves  # is_fallback_valve = true
```

---

### Test 4: Priority Sorting - User Priority and Temperature Deficit

**Purpose:** Verify zones are sorted correctly using priority field and temperature deficit

**Setup (Heating Mode):**
- Zone A (Bedroom): priority=10, target=21°C, current=19°C, deficit=2.0°C
- Zone B (Kitchen): priority=5, target=22°C, current=19°C, deficit=3.0°C
- Zone C (Living): priority=0, target=20°C, current=16°C, deficit=4.0°C
- Zone D (Bathroom): priority=0, target=23°C, current=22°C, deficit=1.0°C

**Expected Sort Order:**
1. Zone A: sort_key=(10, 2.0) - highest user priority
2. Zone B: sort_key=(5, 3.0) - second highest user priority
3. Zone C: sort_key=(0, 4.0) - default priority, largest deficit
4. Zone D: sort_key=(0, 1.0) - default priority, smallest deficit

**Expected Behavior:**
- Zones with user-defined priority (>0) are managed first
- Among zones with same priority, those with higher temperature deficit are managed first
- Zone A gets first attention despite having smaller deficit than C
- Zone C is prioritized over D due to larger deficit (both have priority=0)

---

### Test 5: Valve Lock - Prevent Chattering

**Purpose:** Verify valve locks prevent rapid re-actuation

**Setup:**
- valve_actuation_delay = 120s
- Bedroom valve opened at T=0s

**Timeline:**

| Time | Action | Expected Result |
|------|--------|----------------|
| T=0s | Open Bedroom valve | Success, lock set until T=120s |
| T=30s | Try to close Bedroom valve | BLOCKED (locked) |
| T=90s | Try to close Bedroom valve | BLOCKED (locked) |
| T=120s | Try to close Bedroom valve | Success (lock expired) |

**Expected Behavior:**
- Valve operations within cooldown period are ignored
- Valve lock expires after valve_actuation_delay
- Operations after expiry succeed

---

### Test 6: Cooling Mode - Inverted Logic with Satisfaction Eps

**Purpose:** Verify satisfaction states invert correctly in cooling mode with new satisfaction logic

**Setup (Cooling Mode):**
- opening_offset = 0.3°C
- closing_offset = 0.3°C
- satisfaction_eps = 0.1°C
- HVAC state = COOLING

**Test Cases:**

| Zone | Target | Current | Valve Trigger | Satisfaction Status | Reasoning |
|------|--------|---------|---------------|---------------------|-----------|
| Bedroom | 23.0°C | 25.0°C | OPEN (> 23.3) | Undercooled | 25.0 > 23.1 (target + eps) |
| Living | 24.0°C | 23.9°C | No change | Satisfied | 23.9 <= 24.1 (target + eps), zone falling to target |
| Kitchen | 22.0°C | 21.0°C | CLOSE (< 21.7) | Overcooled | 21.0 < 21.9 (target - eps) |
| Study | 23.0°C | 22.95°C | No change | Satisfied | 22.95 >= 22.9 (target - eps), zone rising to target |

**Cooling Mode Logic:**
- **Valve control**: 
  - Open when: current > (target + opening_offset) = 23.3°C for 23°C target (needs cooling)
  - Close when: current < (target - closing_offset) = 22.7°C for 23°C target (too cool)
- **Satisfaction determination**: Uses satisfaction_eps (0.1°C) around target
  - Satisfied when: (target - 0.1) <= current <= (target + 0.1)
  - For 23°C target: satisfied when 22.9°C to 23.1°C

**Expected Behavior:**
- Bedroom valve opens (undercooled, needs cooling)
- Living Room: satisfied status (reached target while falling), valve maintains state
- Kitchen valve closes (overcooled, too cool)
- Study: satisfied status (reached target while rising from overcooled state)
- Logic correctly inverted from heating mode
- Satisfaction determination still centered around target ± eps

---

### Test 6a: Satisfaction Eps Behavior - Zone Status Transitions

**Purpose:** Verify satisfaction_eps parameter correctly determines when zones transition to satisfied status

**Setup (Heating Mode):**
- Target temperature: 21.0°C
- opening_offset: 0.3°C
- closing_offset: 0.3°C
- Test with different satisfaction_eps values

**Scenario 1: satisfaction_eps = 0.0 (exact target)**

| Current Temp | Valve Action | Satisfaction Status | Reasoning |
|--------------|--------------|---------------------|-----------|
| 20.6°C | OPEN (< 20.7) | Underheated | Not at exact target 21.0°C |
| 20.9°C | No change | Underheated | Not at exact target 21.0°C |
| 21.0°C | No change | Satisfied | Exactly at target |
| 21.1°C | No change | Overheated | Above target |
| 21.4°C | CLOSE (> 21.3) | Overheated | Above target + closing_offset |

**Scenario 2: satisfaction_eps = 0.1°C (±0.1°C buffer)**

| Current Temp | Valve Action | Satisfaction Status | Reasoning |
|--------------|--------------|---------------------|-----------|
| 20.6°C | OPEN (< 20.7) | Underheated | Below (target - eps) = 20.9°C |
| 20.9°C | No change | Satisfied | At (target - eps), zone rising to target |
| 21.0°C | No change | Satisfied | At target |
| 21.1°C | No change | Satisfied | At (target + eps), zone falling to target |
| 21.2°C | No change | Overheated | Above (target + eps) = 21.1°C |
| 21.4°C | CLOSE (> 21.3) | Overheated | Above target + closing_offset |

**Scenario 3: satisfaction_eps = 0.2°C (±0.2°C buffer)**

| Current Temp | Valve Action | Satisfaction Status | Reasoning |
|--------------|--------------|---------------------|-----------|
| 20.6°C | OPEN (< 20.7) | Underheated | Below (target - eps) = 20.8°C |
| 20.8°C | No change | Satisfied | At (target - eps), zone rising to target |
| 21.0°C | No change | Satisfied | At target |
| 21.2°C | No change | Satisfied | At (target + eps), zone falling to target |
| 21.3°C | CLOSE (> 21.3) | Overheated | Above (target + eps) = 21.2°C but triggers valve close |
| 21.4°C | CLOSE (> 21.3) | Overheated | Above target + closing_offset |

**Key Insights:**
- **satisfaction_eps = 0.0**: Strictest - zone must be exactly at target to be satisfied
- **satisfaction_eps = 0.1**: Balanced - provides small buffer for temperature fluctuations
- **satisfaction_eps = 0.2**: More lenient - wider satisfaction band
- Valve control (opening_offset/closing_offset) is independent of satisfaction status
- A zone can have valve open but be "satisfied" if within target ± eps
- This separation allows better status reporting while maintaining proper valve control

**Practical Application:**
- Use satisfaction_eps = 0.0 when exact temperature control is required
- Use satisfaction_eps = 0.1-0.2 for more stable satisfaction status with typical temperature sensor variations
- Larger satisfaction_eps reduces status "flapping" between underheated/satisfied/overheated

---

## Integration Tests

### Test 7: Open-First-Then-Close Sequence

**Purpose:** Verify minimum flow maintained during valve swapping

**Setup:**
- min_valves_open = 1
- valve_actuation_delay = 120s
- Initial: Bedroom valve OPEN
- Scenario: Bedroom satisfied, Kitchen needs heat

**Timeline:**

| Time | Event | Open Valves | Valve States |
|------|-------|-------------|--------------|
| T=0s | Initial | 1 (Bedroom) | Bedroom: OPEN, Kitchen: CLOSED |
| T=0s | Algorithm runs | - | Detect: at minimum, need swap |
| T=0s | Open Kitchen | 1 (Bedroom) | Kitchen opening... |
| T=0-120s | Wait for actuation | 2 (both) | Both valves open (safe) |
| T=120s | Close Bedroom | 1 (Kitchen) | Bedroom closing... |
| T=120-240s | Wait for actuation | 1 (Kitchen) | Kitchen fully open |
| T=240s | Stable | 1 (Kitchen) | Kitchen: OPEN, Bedroom: CLOSED |

**Expected Behavior:**
- At no point do we have 0 valves open
- Kitchen opens before Bedroom closes
- valve_actuation_delay enforced between open and close

---

### Test 8: Multiple Zone Changes - Job Queueing

**Purpose:** Verify job queue handles multiple rapid changes correctly

**Setup:**
- coordinator_interval = 15s
- Initial state: all zones satisfied

**Timeline:**

| Time | Event | Queue State |
|------|-------|-------------|
| T=0s | Bedroom target changed | Queue: [calc_temp_1, update_valves_1] |
| T=5s | Kitchen target changed | Queue: [calc_temp_1, update_valves_1, calc_temp_2, update_valves_2] |
| T=10s | Living Room target changed | Queue: [calc_temp_1, update_valves_1, calc_temp_2, update_valves_2, calc_temp_3, update_valves_3] |
| T=15s | Coordinator runs | Dequeue calc_temp_1 → execute |
| T=15s | Coordinator runs | Dequeue update_valves_1 → execute |
| T=30s | Coordinator runs | Dequeue calc_temp_2 → execute |
| T=30s | Coordinator runs | Dequeue update_valves_2 → execute |
| T=45s | Coordinator runs | Dequeue calc_temp_3 → execute |
| T=45s | Coordinator runs | Dequeue update_valves_3 → execute |

**Expected Behavior:**
- Jobs queued in FIFO order
- Only one job of each type runs at a time (job locks)
- All jobs eventually processed
- No jobs lost

---

### Test 9: Multizone Feature OFF - Individual Zone Control

**Purpose:** Verify system behavior when multizone feature is disabled

**Setup:**
- Initial: Bedroom valve open (underheated), Kitchen valve open (satisfied), Living Room valve closed (overheated)
- Multizone feature turned OFF

**Expected Behavior:**
1. Each zone manages its own valve based on satisfaction state
2. Underheated zones: valves open
3. Overheated zones: valves close
4. Satisfied zones: maintain current valve state
5. Safety check still runs to ensure minimum valves open
6. No coordinated multi-zone logic (each zone independent)

**Example:**
- Bedroom (underheated, 19°C, target 21°C): valve OPEN
- Kitchen (overheated, 23°C, target 20°C): valve CLOSE
- Living Room (satisfied, 22°C, target 22°C): valve maintains current state

**Rationale:**
- When multizone OFF, each zone operates independently
- Zones still react to temperature (underheated → open, overheated → close)
- Cannot trust HVAC status alone (pump may still circulate)
- Safety check ensures system protection

---

### Test 10: Main Climate OFF - No Automatic Changes

**Purpose:** Verify system safety when main HVAC turns off

**Setup:**
- Initial: 3 valves open, multizone feature enabled
- Main climate state changes to OFF

**Expected Behavior:**
1. System behavior depends on multizone state
2. If multizone enabled: continue managing valves (HVAC may still circulate)
3. If multizone disabled: user has manual control
4. Safety check always runs to maintain minimum valves

**Rationale:**
- HVAC OFF doesn't necessarily mean no circulation
- Pump may continue running in some systems
- Multizone feature state determines control mode
- Safety minimum always applies when multizone is active

---

### Test 11: Job Lock - Prevent Concurrent Execution

**Purpose:** Verify job locks prevent concurrent execution of same job type

**Setup:**
- Two "update_valves" jobs in queue
- Job execution time: 5 seconds

**Timeline:**

| Time | Event | Job Lock State |
|------|-------|----------------|
| T=0s | Job1 starts | Lock acquired: update_valves |
| T=2s | Job2 tries to start | BLOCKED (lock held) |
| T=5s | Job1 completes | Lock released |
| T=5s | Job2 starts | Lock acquired: update_valves |
| T=10s | Job2 completes | Lock released |

**Expected Behavior:**
- Only one job runs at a time
- Second job waits for first to complete
- No race conditions or data corruption

---

### Test 12: Configuration Change - Dynamic Updates

**Purpose:** Verify system responds to configuration changes

**Setup:**
- Initial: min_valves_open = 1
- Change: min_valves_open = 2
- Currently: 1 valve open

**Expected Behavior:**
1. Configuration updated in Redis
2. Next "safety_valve_check" detects shortage
3. Force open additional fallback valve
4. Final state: 2 valves open

**Test Assertion:**
```python
update_config("min_valves_open", 2)
trigger_safety_check()
assert len(get_open_valves()) == 2
```

---

## Test Coverage Goals

- **Unit Tests:** 90%+ coverage for core algorithms
- **Integration Tests:** All job types, automation triggers, safety checks
- **Edge Cases:** Empty zones, all satisfied, all OFF, cooling mode
- **Performance Tests:** 100 zones, rapid changes, queue saturation
- **Reliability Tests:** Redis connection loss, entity unavailability

---

# !!! Important Functional Rules !!!
- This should be a valid Home Assistant integration via HACS
- Redis is used for holding and sharing data between different async processes (or parallel processes)
- Redis could be a good place to hold current background job statuses
- Update entity states resp. values only when they have changed!
- Required minimum valves opened - safety check of this is important!
- Multizone feature runs only when manual switch is on and at least 1 climate zone (ON) present
- When there is a minimum required valve fully opened, and we want to close one and open another one, in this case we have to open one first, wait for the physical valve opening delay configured by the user (to fully open the valve), and then close the second one.
  This could be held by Redis with valve ID and timestamp when it can be closed.
- If there are a minimum of N required valves configured, there have to be N fallback valves configured as well
- When a multizone climate entity is set to OFF, it basically closes its valve and is skipped from multizone feature computing. (Only when it is a fallback valve, it can be opened for safety reasons even though the zone climate entity state is OFF)

# Code Rules
- Code should be clean and easily readable
- Code should be commented, including what each method does and describing params as well
- Code should be well tested

# UI Frontend
- Integration setup should be nice, cool, user-friendly and value change responsive with validations
- There should be a nice and user-friendly config editor to change config values stored in Redis
- Option to manage climate zones - add, update, delete (some dynamic form with add and remove buttons)

# Dashboards and Cards (lovelace)
- Climate zone entity card (usable for each climate zone entity)
- Main climate entity card (usable for main climate entity)
- Dashboard to manage climate zone entities (at all times) and main climate entity (when multizone feature is off; otherwise entity is driven by multizone feature)
- Dashboard to monitor metrics (states, sensors, actions) - for monitoring and debugging purposes

# IDEAS
- Maybe passing how the heating curve is configured on the HVAC unit would help to calculate target temperature more precisely
- Maybe there are more things that would be good to be managed via Redis storage for some reasons
- We will probably need to create our own climate entity card due to custom features, but it should look similar to the thermostat card <THERMOSTAT_CARD_IMAGE>
- I am pretty sure there have to be more custom JS components implemented to create specific cards and dashboards for multizone management purposes

# Sources and documentations
## Home Assistant Developers Docs
- Webpage: https://developers.home-assistant.io/
- GitHub: https://github.com/home-assistant
- Interesting urls:
  - https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job/
  - https://developers.home-assistant.io/docs/development_index
  - https://github.com/home-assistant/core
  - https://github.com/home-assistant/supervisor
  - https://github.com/home-assistant/frontend
  - https://www.thecandidstartup.org/2025/10/20/home-assistant-concurrency-model.html
## HVAC unit climate entity custom component
- https://github.com/Chester929/remeha_home_by_chester - master branch
## Lovelace
- https://github.com/project-lovelace
## De Dietrich HVAC Unit
- https://www.dedietrich-vytapeni.cz/tepelna-cerpadla/strateo-vzduch-voda-split-inverter-s-vestavenym-ohrivacem-tv/
- https://www.dedietrich-vytapeni.cz/index.php?cmd=download&id=9370&type=view
- https://www.dedietrich-vytapeni.cz/index.php?cmd=download&id=9611&type=view
- https://www.dedietrich-vytapeni.cz/index.php?cmd=download&id=10147&type=view
## Main climate Thermostat
- https://www.dedietrich-vytapeni.cz/prislusenstvi/smart-tc-ad324-inteligentni-regulator-teploty-prostoru/
- https://www.dedietrich-vytapeni.cz/index.php?cmd=download&id=4628&type=view

---

# Future Improvements

While the current design uses a slider-based approach for calculating the main climate target temperature, future versions could incorporate more sophisticated control strategies:

## PI (Proportional-Integral) Controller Option

Instead of the simple slider mapping, implement a PI controller to more dynamically adjust the main target based on zone performance:

```python
def calculate_main_target_pi(zones, config, state):
    """
    PI controller for main target temperature.
    
    Args:
        zones: Climate zones with current and target temps
        config: Kp (proportional gain), Ki (integral gain)
        state: Maintains integral error accumulation
    
    Returns:
        Main target temperature
    """
    # Calculate total error (sum of zone temperature deficits)
    total_error = sum(z.target_temp - z.current_temp for z in zones)
    
    # Update integral
    state.integral_error += total_error * dt
    
    # PI formula
    main_target = base_temp + (config.Kp * total_error) + (config.Ki * state.integral_error)
    
    return clamp(main_target, config.main_min_temp, config.main_max_temp)
```

**Benefits:**
- More responsive to zone heating demands
- Automatically adjusts to building thermal characteristics
- Reduces overshoot and steady-state error

**Challenges:**
- Requires tuning Kp and Ki parameters for specific installations
- More complex for users to understand
- May need anti-windup protection for integral term

## Heating Curve Integration

Leverage the HVAC unit's heating curve configuration to optimize main target calculation:

```python
def calculate_with_heating_curve(zones, outdoor_temp, heating_curve_config):
    """
    Adjust main target based on heating curve and outdoor temperature.
    
    Args:
        zones: Climate zones
        outdoor_temp: Current outdoor temperature
        heating_curve_config: Base temp, slope from HVAC unit
    
    Returns:
        Optimized main target
    """
    # Standard zone-based target
    zone_target = calculate_zone_based_target(zones)
    
    # Heating curve suggests water temperature
    water_temp = heating_curve_config.base - (heating_curve_config.slope * outdoor_temp)
    
    # Blend zone needs with heating curve
    main_target = blend(zone_target, water_temp, blend_factor=0.7)
    
    return main_target
```

**Benefits:**
- Works with HVAC's existing thermal model
- Better outdoor temperature compensation
- Potentially faster heating response

**Implementation Note:**
- Would require users to input heating curve parameters from their HVAC unit
- May need calibration period to determine optimal blend factor

## Adaptive Learning

Track zone heating/cooling performance over time and adjust strategy:

- **Learning rate:** How quickly zones reach target at different main temperatures
- **Thermal mass:** Estimate building thermal inertia
- **Time-of-day patterns:** Learn typical heating needs by hour
- **Weather compensation:** Correlate outdoor temp with required main target offset

These improvements could be added as optional advanced features while maintaining the simple slider approach as the default for ease of use.
