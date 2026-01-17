# Home Assistant Service API Client Documentation

## Overview

The Home Assistant Service API Client provides direct integration with Home Assistant without requiring MQTT. It offers two communication methods:

1. **HTTP REST API** - For reading entity states and calling services
2. **WebSocket API** - For real-time state change notifications

## Features

### Core Capabilities

- ✅ Read entity states (temperature sensors, switches, climate entities)
- ✅ Call Home Assistant services (turn on/off switches, set temperature)
- ✅ Real-time WebSocket subscriptions for state changes
- ✅ Automatic synchronization of states to Redis
- ✅ Trigger automatic recalculations on temperature changes
- ✅ Entity type auto-detection (temperature sensors, valves, climate entities)
- ✅ Connection health monitoring and error handling

### API Endpoints

The integration adds the following REST endpoints to the logic container:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ha/status` | GET | Get HA integration status and WebSocket connection state |
| `/api/ha/test` | GET | Test Home Assistant API connectivity |
| `/api/ha/sync` | POST | Manually trigger state synchronization |
| `/api/ha/valve` | POST | Control a valve switch through HA |
| `/api/ha/temperature` | POST | Set main climate temperature through HA |

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Home Assistant API Configuration
HA_ENABLED=true
HA_BASE_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token_here
HA_WEBSOCKET=true
```

### Configuration Details

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HA_ENABLED` | No | `false` | Enable Home Assistant integration |
| `HA_BASE_URL` | Yes* | `http://homeassistant.local:8123` | Home Assistant URL |
| `HA_TOKEN` | Yes* | - | Long-lived access token from HA |
| `HA_WEBSOCKET` | No | `true` | Enable WebSocket for real-time updates |

*Required when `HA_ENABLED=true`

### Getting a Long-Lived Access Token

1. In Home Assistant, go to your profile (click your name in sidebar)
2. Scroll to "Long-Lived Access Tokens" section
3. Click "Create Token"
4. Give it a name (e.g., "Multizone Climate")
5. Copy the token immediately (it won't be shown again)
6. Use this token as the `HA_TOKEN` value

## Usage

### Automatic Operation

When enabled, the integration automatically:

1. **On Startup:**
   - Connects to Home Assistant API
   - Establishes WebSocket connection
   - Performs initial state synchronization
   - Subscribes to state change events

2. **During Operation:**
   - Monitors temperature sensor changes
   - Updates Redis with new temperature values
   - Triggers recalculation when temperatures change
   - Tracks valve state changes
   - Monitors main climate entity state

3. **On Shutdown:**
   - Gracefully closes WebSocket connection
   - Cleans up resources

### Manual API Calls

#### Check Integration Status

```bash
curl http://localhost:8080/api/ha/status
```

Response:
```json
{
  "enabled": true,
  "websocket": true,
  "time": "2026-01-16T20:00:00Z"
}
```

#### Test Connection

```bash
curl http://localhost:8080/api/ha/test
```

Response (success):
```json
{
  "connected": true,
  "message": "Home Assistant connection successful"
}
```

Response (failure):
```json
{
  "connected": false,
  "error": "connection refused"
}
```

#### Manually Sync States

```bash
curl -X POST http://localhost:8080/api/ha/sync
```

Response:
```json
{
  "status": "success",
  "message": "States synchronized successfully"
}
```

#### Control a Valve

```bash
curl -X POST http://localhost:8080/api/ha/valve \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "switch.bedroom_valve",
    "open": true
  }'
```

Response:
```json
{
  "status": "success",
  "entity_id": "switch.bedroom_valve",
  "state": {"open": true}
}
```

#### Set Main Temperature

```bash
curl -X POST http://localhost:8080/api/ha/temperature \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "climate.main_thermostat",
    "temperature": 22.5
  }'
```

Response:
```json
{
  "status": "success",
  "entity_id": "climate.main_thermostat",
  "temperature": 22.5
}
```

## Zone Configuration

### Entity ID Mapping

Each zone in Redis should have the following fields configured:

```redis
HSET multizone:zone:bedroom temperature_sensor_entity_id "sensor.bedroom_temperature"
HSET multizone:zone:bedroom valve_switch_entity_id "switch.bedroom_valve"
```

### Global Configuration

Configure the main climate entity:

```redis
HSET multizone:config main_climate_entity_id "climate.main_thermostat"
```

## Real-Time State Updates

### How It Works

1. **WebSocket Connection:**
   - Establishes WebSocket connection to HA
   - Authenticates using long-lived access token
   - Subscribes to `state_changed` events

2. **Event Processing:**
   - Receives state change events in real-time
   - Identifies entity type (temperature sensor, valve, climate)
   - Updates corresponding Redis data

3. **Automatic Recalculation:**
   - Temperature changes trigger calculation jobs
   - Jobs are queued in Redis (`multizone:job_queue`)
   - Worker pool processes jobs asynchronously

### Supported Entity Types

#### Temperature Sensors
Auto-detected by:
- `device_class: temperature` attribute
- `unit_of_measurement: °C` or `°F` attribute

#### Valve Switches
Detected by matching `valve_switch_entity_id` in zone configuration

#### Climate Entities
Detected by matching `main_climate_entity_id` in global configuration

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Logic Container                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Home Assistant Integration                   │  │
│  │                                                      │  │
│  │  ┌─────────────┐        ┌──────────────┐           │  │
│  │  │ HTTP Client │◄──────►│ HA REST API  │           │  │
│  │  └─────────────┘        └──────────────┘           │  │
│  │                                                      │  │
│  │  ┌─────────────┐        ┌──────────────┐           │  │
│  │  │ WS Client   │◄──────►│ HA WebSocket │           │  │
│  │  └─────────────┘        └──────────────┘           │  │
│  │         │                                            │  │
│  │         ▼                                            │  │
│  │  ┌─────────────┐                                    │  │
│  │  │   Redis     │                                    │  │
│  │  │   Updates   │                                    │  │
│  │  └─────────────┘                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Package Structure

```
logic/internal/homeassistant/
├── client.go         # HTTP REST API client
├── client_test.go    # HTTP client tests (11 tests)
├── websocket.go      # WebSocket client
└── integration.go    # Integration layer with Redis
```

### Key Types

#### Client (HTTP)
```go
type Client struct {
    baseURL    string
    token      string
    httpClient *http.Client
}
```

Methods:
- `GetState(ctx, entityID)` - Get entity state
- `GetStates(ctx)` - Get all states
- `CallService(ctx, call)` - Call any service
- `TurnOnSwitch(ctx, entityID)` - Turn on switch
- `TurnOffSwitch(ctx, entityID)` - Turn off switch
- `SetTemperature(ctx, entityID, temp)` - Set climate temperature
- `SetHVACMode(ctx, entityID, mode)` - Set HVAC mode
- `Ping(ctx)` - Test connection

#### WebSocketClient
```go
type WebSocketClient struct {
    baseURL       string
    token         string
    conn          *websocket.Conn
    subscriptions map[int64]*Subscription
    eventHandlers map[string]EventHandler
}
```

Methods:
- `Connect(ctx)` - Establish WebSocket connection
- `SubscribeToStateChanges(handler)` - Subscribe to state changes
- `SubscribeToEvents(eventType, handler)` - Subscribe to specific events
- `Unsubscribe(subscriptionID)` - Unsubscribe from events
- `Close()` - Close connection
- `IsConnected()` - Check connection status

#### Integration
```go
type Integration struct {
    client           *Client
    wsClient         *WebSocketClient
    redisClient      *redis.Client
    enabled          bool
    websocketEnabled bool
}
```

Methods:
- `Start()` - Start integration
- `Stop()` - Stop integration
- `SyncAllStates(ctx)` - Sync all entity states
- `SetValveState(ctx, entityID, open)` - Control valve
- `SetMainTemperature(ctx, entityID, temp)` - Set temperature
- `IsEnabled()` - Check if enabled

## Testing

### Running Tests

```bash
cd logic
go test ./internal/homeassistant/... -v
```

### Test Coverage

The implementation includes 11 comprehensive tests:

1. `TestNewClient` - Client creation
2. `TestGetState` - Get single entity state
3. `TestGetStates` - Get all states
4. `TestCallService` - Generic service call
5. `TestTurnOnSwitch` - Switch on
6. `TestTurnOffSwitch` - Switch off
7. `TestSetTemperature` - Climate temperature
8. `TestSetHVACMode` - HVAC mode
9. `TestPing` - Connection test
10. `TestGetStateError` - Error handling
11. `TestCallServiceError` - Service error handling

All tests use mock HTTP servers for isolated testing.

## Troubleshooting

### Integration Not Starting

**Symptom:** Log shows "Home Assistant integration is disabled"

**Solution:**
1. Check `HA_ENABLED=true` in environment
2. Verify `HA_TOKEN` is set and valid
3. Check Home Assistant is accessible at `HA_BASE_URL`

### WebSocket Connection Fails

**Symptom:** Log shows "failed to start websocket"

**Possible Causes:**
1. Invalid access token
2. Home Assistant not accessible
3. WebSocket port blocked by firewall
4. SSL/TLS certificate issues

**Solution:**
1. Test HTTP API first: `curl http://localhost:8080/api/ha/test`
2. Verify token in Home Assistant UI
3. Check network connectivity
4. Try `HA_WEBSOCKET=false` to disable WebSocket temporarily

### States Not Syncing

**Symptom:** Temperature changes not reflected in Redis

**Solution:**
1. Check entity IDs are correct in zone configuration
2. Verify WebSocket is connected: `GET /api/ha/status`
3. Check Home Assistant entity states are changing
4. Enable debug logging: `LOG_LEVEL=debug`
5. Manually trigger sync: `POST /api/ha/sync`

### Authorization Errors

**Symptom:** 401 Unauthorized errors

**Solution:**
1. Regenerate long-lived access token
2. Update `HA_TOKEN` environment variable
3. Restart logic container

## Performance Considerations

### Resource Usage

- **Memory:** ~5-10 MB additional for HA integration
- **CPU:** Minimal (<1%) when idle
- **Network:** WebSocket maintains single connection
- **Redis:** Additional writes on state changes

### Scalability

- Single WebSocket connection handles all events
- Event processing is asynchronous
- Redis updates are queued
- No polling - fully event-driven

### Rate Limiting

Home Assistant applies rate limits:
- API calls: ~100/minute typical limit
- WebSocket: No practical limit
- Use WebSocket for frequent updates
- Batch API calls when possible

## Migration from MQTT

### Comparison

| Feature | MQTT | HA Service API |
|---------|------|----------------|
| Setup Complexity | Medium | Low |
| Entity Creation | Auto-discovery | Uses existing entities |
| Real-time Updates | Yes | Yes (WebSocket) |
| Network Overhead | Medium | Low |
| HA Restart Impact | None | Reconnects automatically |
| Dependencies | MQTT Broker | None |

### Migration Steps

1. Configure HA integration (see Configuration section)
2. Update zone entity IDs to match existing HA entities
3. Test with `HA_WEBSOCKET=false` first
4. Enable WebSocket once stable
5. Disable MQTT middleware if no longer needed

### Running Both

MQTT and HA Service API can run simultaneously:
- MQTT provides new entities for control
- HA Service API monitors existing entities
- Choose one as primary, other as backup

## Security

### Best Practices

1. **Token Security:**
   - Never commit tokens to version control
   - Use environment variables or secrets management
   - Rotate tokens periodically
   - Use separate token per integration

2. **Network Security:**
   - Use HTTPS for `HA_BASE_URL` when possible
   - Consider VPN for remote access
   - Firewall rules to limit access
   - Monitor access logs

3. **Access Control:**
   - Create dedicated HA user for integration
   - Limit user permissions to required entities
   - Review token permissions regularly

## Logs and Monitoring

### Log Messages

The integration logs the following events:

```
INFO: Initializing Home Assistant integration...
INFO: Home Assistant API connection successful
INFO: WebSocket connection established and subscribed to state changes
INFO: Initial state synchronization completed
INFO: State changed: sensor.bedroom_temperature -> 21.5
INFO: Updated zone temperature: multizone:zone:bedroom -> 21.50°C
```

### Monitoring Endpoints

Check integration health:
```bash
# Overall status
curl http://localhost:8080/status

# HA-specific status
curl http://localhost:8080/api/ha/status
```

## Advanced Usage

### Custom Event Handlers

The integration can be extended to handle additional event types:

```go
// Subscribe to custom events
_, err := wsClient.SubscribeToEvents("automation_triggered", func(event *Event) {
    log.Printf("Automation triggered: %v", event.Data)
})
```

### Direct Client Usage

Access the underlying clients for advanced use cases:

```go
// Get the HTTP client
httpClient := integration.GetClient()

// Get specific entity state
state, err := httpClient.GetState(ctx, "sensor.custom")

// Get the WebSocket client
wsClient := integration.GetWebSocketClient()

// Check connection
if wsClient.IsConnected() {
    // Do something
}
```

## FAQ

**Q: Can I use this without WebSocket?**
A: Yes, set `HA_WEBSOCKET=false`. Manual sync will still work via API.

**Q: Does this replace MQTT?**
A: It's an alternative. Choose based on your needs - MQTT creates new entities, HA API uses existing ones.

**Q: How often are states synced?**
A: WebSocket provides instant updates. Manual sync can be triggered anytime via API.

**Q: What happens if Home Assistant restarts?**
A: WebSocket will attempt to reconnect automatically. States resync on reconnection.

**Q: Can I control multiple Home Assistant instances?**
A: Currently one instance per logic container. Run multiple containers for multiple HA instances.

**Q: Is authentication secure?**
A: Yes, uses long-lived access tokens over HTTPS when configured properly.

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/Chester929/ha_multizone_climate/issues
- Documentation: See IMPLEMENTATION.md and DIAGRAMS.md
- Examples: See examples/ directory

## Version History

- **v2.1** (2026-01-16) - Added Home Assistant Service API Client
  - HTTP REST API integration
  - WebSocket real-time updates
  - Comprehensive test coverage
  - Full documentation

## License

MIT License - See LICENSE file for details
