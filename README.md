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
- Calculate main temperature
  - TBD
- Update valves
  - TBD
- Safety valve check
  - Checks if the minimum required number of valves are open
  - If not, log a warning and open fallback valves.
- Background jobs
  - Process locker (redis can be used)
    - At the same time there can be only one running job per type
      - Update valves
      - Calculate main target temperature
      - Safety valve check
  - Managing background jobs using queues
    - 2 FIFO queues - one for Update valves and one for Calculate main target temperature

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
