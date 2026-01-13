# ha_multizone_climate
Home Assistant Automation integration to better manage heat zones.

# Whats the issue
I have HVAC unit driven by one thermostat using heating curve to count correct temperature in pipes.
I would like to manage temperature per room by sensors and valve controllers.
The HVAC is missing cyrculating line so there has to be at least one valve still open.

## Main Climate unit and Thermostat
I have HVAC unit which is controlled by one thermostat throug physical cables.
This thermostat is placed in corridor and it has own temperature sensor.
HVAC unit using this thermostats temperature sensor along side with outside temperature sensor, to count how to heat water to heat or hold temperature inside by "heating curve".
Heating curve is configured in UNIT: "heating curve deviation (base)" = 15.0°
                                     "increase" = 0.5
That means when outside is 25°C the water temperature in heating pipes is 0°C, when outside is 15°C in pipes is 20°C.
HVAC is also cooling when outside temperature is higher then target inside but does not have sensor for it.
We can change this two options to get better result in the future, but thats the unit configuration thing.

The thermostat can be driven remotely through cloud API (It has network connection over WiFi to connect to the cloud).
I have smart home driven by Home Assistant. I already have custom component which produce custom climate entity
to drive thermostat through API (cloud). You can find this custom component there https://github.com/Chester929/remeha_home_by_chester.
I can drive over API target temperature and HVAC mode (OFF (Anti-Freeze), Manual, Scheduler)

There is also another climate component to drive DWH (boiler) to heat hot water for the house. But it is separate feature of the HVAC unit and it has own drive entity.
Boiler is not part of this issue.

## Heat zones
I already have temperature sensors in my other rooms integrated with Home Assistant over temperature sensor.
There are also heat pipe valves (open/close) for each room driven remotely and integrated with Home Assistant over switch entity.

# Whats the goal
I would like to implement Home Assistant intgeration which will effectively manage heating system over valve controllers,
temperature sensors and targeting the right temperature on the main HVAC thermostat by setuped target temperatures for different rooms by user.
It has to be clean code, nice, effective, fast, and safe! Also this component should be able to be installed over HACS into Home Assistant.

## Project Architecture draft
 - MAIN CLIMATE DEVICE (Main Climate Entity from config entry)
   - Temperature Sensor - Main climate target temperature
   - Temperature Sensor - Main climate current temperature
   - Temperature Sensor - Outdoor temperature
   - Climate hvac mode (OFF (Anti-Freeze), MANUAL, SCHEDULING)
   - state (OFF, HEATING, COOLING)
     - cooling when Main climate target temperature is lower then outdoor temperature
     - off/on state
       - maunal switch on/off
       - when there are not any climate zone present yet, switch is not editable and its set to off
       - when hvac mode is OFF then on/off switch is not editable and its set to off
       - when off climate zones are not managed by multizone feature, but every climate zone just drives his own valve by own target and current temperature
 - CLIMATE ZONE SUBDEVICES ( Climate device per room )
   - name
   - state (off, underheated, satisfied, overheated) resp. (off, overcooled, satisfied, undercooled) when cooling.
   - temperature sensor
   - valve switch
   - target change threshold
   - opening offset below target
   - closing offset above target
 - REDIS CONFIG ( redis required )
   - host
   - port
   - credentials
 - CONFIG
   - All zones satisfied temperature target
   - Minimum valves open
   - Main climate min/max temperature
   - Main climate target temperature change trashold
   - Physical valve opening/closing delay
 - **CORE LOGIC
   - helper methods respecting config described later
 - BACKGROUND ASYNC JOBS (3 jobs)
   - Udate valves
     - invoked by "Update main target temperature" automation
     - job identifier ( used for debugging and job status )
     - run core logic inside to manage physical valves
   - Calculate main target temperature
     - invoked by "Update main target temperature" automation
     - job identifier ( used for debugging and job status )
     - run core logic inside to calculate temperature
   - Safety valve check
     - invoked by "Safety valve check" automation
     - job identifier ( used for debugging and job status )
     - run core logic inside to check minimum valves open
 - AUTOMATIONS (2 automations - Listens to events or time entity nad invokes async job)
   - Update main target temperature
     - invoked only when one(or more) of zones temperature or target temperature has been changed
     - add "Calculate main target temperature" async job with current parameters into its process queue
     - add "Udate valves" async job with current params into its process queue
   - Safety valve check
     - invoked every half of "Physical valve opening/closing delay" configured time (if configured delay is 0, then every 1m)
     - directly invoke "Safety valve check" async job
 - COORDINATOR (runs every 15s)
   - reads current entities data through core logic redis client and:
     - updates sensors
     - updates 
   - dequeue "Udate valves" background async job from its queue and invoke it (if any in the queue and no other running)
   - dequeue "Calculate main target temperature" background async job from its queue and invoke it (if any in the queue and no other running)
 - LOGGER (Logging)
   - INFO
   - WARN
   - ERROR
   - DEBUG
 - LOCALS (Translations (en, cz, sk, pl))
 - TESTS
   - every single background job test with different scenarios(parameters)
   - coordinator test
   - core logic test
   - home assistant integration test per each entity (sensor, climate, etc)
 - LINTNERS (Code quality and security checks)
 - DOCUMENTATION
 - FRONTEND (cool and user friendly lovelace cards and dashboards to monitor sensors and manage climate entities)


## **Core logic
Initialize and holds redis client instance to read global config and entities data.

### Find main climate target temperature
Inputs:
  - Main climate
    - current temperature
    - current target temperature
  - Changed climate zones:
    - current temperature
    - target temperature
    - valve switch
   
Steps:
  - fetch config from redis
  - fetch data from redis
  - calculate target temperature
  - hass.service.call to update main climate entity target temperature
  - update data to redis 

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
  - fetch config from redis
  - fetch data from redis
  - check satisfaction
  - update status
  - hass.service.call to open/close valve for each zone (respect at least one valve has to be open - fallback can be used if necessary)
  - update data to redis

## Integration Setup
When creating integration, there will be inputs for:
  - Redis connection configuration
    - host, port, credentials, keys prefix (default: empty)
  - Main Climate Entity reference - this will be used as target entity to read/write their target temperature and read their current temperature
  - Automation Configuration:
    - Main Target When All Zones Satisfied (slider 0-100%) - What to set the main climate target when all zones have reached their targets
      - 0% = Use lowest zone target (energy efficient)
      - 50% = Use average zone target (balanced approach, default)
      - 100% = Use highest zone target (keeps boiler warmer)
    This is used to HOLD temperatures in the rooms when all zones satisfied.
  - Minimum Valves Open: Number of valves to keep open at all times for system safety (default: 1)
  - Main Min/Max Temperature: Temperature range for main climate entity (HVAC unit) (default: 18.0-30.0°C)
  - Main Change Threshold: Minimum temperature change to update main climate (default: 0.5°C)

This should setup main climate device, which will be monitoring and managing main climate entity.
Once the integration is created, there is nothing to manage yet except main climate. We just can see actual main climate target temperature. User has option to add
climate zone. This part will create climate entity for the zone (something like Generic Thermostat in HA).
When there is at least 1 zone turned ON, multizone feature can be turned on by manual switch.
When multizone future turned on, automatizations resp. calculations are turned on.

## Add Climate Zone
Inputs:
  - Climate zone name (ex: Bedroom)
  - Climate zone temperature sensor - temperature sensor entity (thats temperature sensor in the room)
  - Climate zone valve switch - switch entity (thats controlls heat pipe valve to open/close for the room)
  - Climate zone target change treshold - whats the step to change target temperature. ( Default: 0.1 )
  - Climate zone opening offset below target - temperature offset below target to trigger valve opening (default: 0.3°C)
  - Climate closing offset above target - temperature offset above target to trigger valve closing (default: 0.3°C)
This climates should be as subdevices of the main device which holds main climate entity target temperature sensor and core automation as well.
This zone climate entities drives target temperature, but they does not driving valves,
they are just informating about current temperature, target temperature and satisfaction status in the zone.

# Algorythms
- Calculate main temperature
  - TBD
- Update valves
  - TBD
- Safety valve check
  - Checks if minimum required opened valves is open
  - if not log warning and open fallback valves.
- Background jobs
  - Process locker (redis can be used)
    - at the same time there can be runned only one job per type
      - Udate valves
      - Calculate main target temperature
      - Safety valve check
  - Managing background jobs using queues
    - 2 FIFO queues - one for Udate valves and one for Calculate main target temperature

# !!! Important functional rules !!!
- this should be valid Home Assistant integration over HACS
- redis is used for holding and sharing data between differen async processes (or parralel processes)
- redis could be good place to hold current background job statuses
- update entity states resp values only when they changed!
- required minimum valves opened - safety check of this is important!
- multizone feature runs only when manual switch is on and at least 1 climate zone (ON) present.
- when tehere is minimum required valve fully opened, and we want to close one and open another one, in this case
  we have to open one first, wait for physical valve opening delay setupped by user (to fully open valve) and then close the second one.
  This could be holded by redis with valve id and timestempe when it can be closed.
- if there is minimum required valves configured to N, there has to be N fallback valves configured as well
- when multizone climate entity is set to OFF, it basicaly closes its valve and its skipped from multizone future computing. (only when it is an fallback valve, it can be opened for safety reasons however zone climate entity state is OFF)

# Code rules
- code should be clean and easy readable
- code should be commented including what method is doing describing params as well
- code should be well tested

# UI Frontend
- integration setup should be nice, cool, user-friendly and value change responsive with validations
- there should be some nice and user friendly config editor, to change config values stored in redis
- option to manage climate zones - add, update, delete (some dynamic form with adding and removing button)

# Dashboards and Cards (lovelace)
- climate zone entity card (usable for each climate zone entity)
- main climate entity card (usable for main climate entity)
- dashboard to manage climate zone entities (every time) and main climate entity (when multizone feature is off, otherwise entity is driven by multizone feature)
- dashboard to monitoring metrics (states, sensors, actions) - for monitoring and debugging purposes

# IDEAS
- maybe passing how heating curve is setupped on HVAC unit would help to calculate target temperature more precisely
- maybe there are more things good to be driven via redis storage for some reasons
- probably we will need to create own climate entity card due to own features, but it should looks similar to thermostat card <THERMOSTAT_CARD_IMAGE>
- I am pretty shure there has to be more custom js components implemented to create specic cards and dashboards multizone management purposes

# Sources and documentations
## Home Assitant Developers Docs
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
