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

## Integration Setup
When creating integration, there will be inputs for:
 - Main Climate Entity reference - this will ne used as target entity to manage their target temperature
 - Automation Configuration:
   - Main Target When All Zones Satisfied (slider 0-100%) - What to set the main climate target when all zones have reached their targets
      - 0% = Use lowest zone target (energy efficient)
      - 50% = Use average zone target (balanced approach, default)
      - 100% = Use highest zone target (keeps boiler warmer)
     This is used to HOLD temperatures in the rooms.
   - Minimum Valves Open: Number of valves to keep open at all times for system safety (default: 1)
   - Main Min/Max Temperature: Temperature range for main climate entity (HVAC unit) (default: 18.0-30.0°C)
   - Main Change Threshold: Minimum temperature change to update main climate (default: 0.5°C)

This should setup main device, which will be holding reference to main climate, it can have sensor to show actual main climate target temperature.
Once the integration is created, there is nothing to manage yet. We just can see actual main climate target temperature. User has option to add
climate zone. This part will create climate entity for the zone (somthing like Generic Thermostat in HA).

## Add Climate Zone
Inputs:
  - Climate zone name (ex: Bedroom)
  - Climate zone temperature sensor - temperature sensor entity (thats temperature sensor in the room)
  - Climate zone valve switch - switch entity (thats controlls heat pipe valve to open/close for the room)
  - Climate zone target change treshold - whats the step to change target temperature. ( Default: 0.1 )
  - Climate zone opening offset below target - temperature offset below target to trigger valve opening (default: 0.3°C)
  - Climate closing offset above target - temperature offset above target to trigger valve closing (default: 0.3°C)
This climates should be as subdevices of the main device which holds main climate entity target temperature sensor and core automation as well.
This zone climates does not driving valves, they are just informating about current temperature and target temperature in the zone.

## Core logic
There should be some effective and quick automation to manage climate zones temperatures by opening and closing valves and setting up the right temperature on main climate entity temperature target.
#TODO
