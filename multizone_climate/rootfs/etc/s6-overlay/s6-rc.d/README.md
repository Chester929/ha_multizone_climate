# S6-Overlay Service Structure

This directory contains the s6-overlay service definitions for the Multizone Climate add-on.

## Services

### init (oneshot)
- **Type**: oneshot (runs once at startup)
- **Purpose**: Initializes the add-on and installs the custom component
- **Location**: `/config/custom_components/multizone_climate` (or `/homeassistant/custom_components` as fallback)
- **Dependencies**: None (runs first)

### redis (longrun)
- **Type**: longrun (supervised daemon)
- **Purpose**: Redis server for state management
- **Dependencies**: None

### logic (longrun)
- **Type**: longrun (supervised daemon)
- **Purpose**: GoLang logic server providing the backend API
- **Dependencies**: init, redis

## Service Execution Order

1. **init** - Installs custom component to Home Assistant
2. **redis** - Starts Redis server
3. **logic** - Starts logic server (depends on both init and redis)

All services are included in the "user" bundle which is managed by s6-overlay.
