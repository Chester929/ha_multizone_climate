package homeassistant

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"sync"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
)

// Integration manages the Home Assistant integration
type Integration struct {
	client           *Client
	wsClient         *WebSocketClient
	redisClient      *redis.Client
	enabled          bool
	websocketEnabled bool
	// Entity ID to zone key mapping cache for O(1) lookups
	entityCache struct {
		sync.RWMutex
		tempSensorToZone map[string]string // temperature_sensor_entity_id -> zone_key
		valveToZone      map[string]string // valve_switch_entity_id -> zone_key
		climateToZone    map[string]string // climate_entity_id -> zone_key
		mainClimateID    string            // main_climate_entity_id
	}
}

// NewIntegration creates a new Home Assistant integration
func NewIntegration(baseURL, token string, redisClient *redis.Client, enableWebSocket bool) *Integration {
	i := &Integration{
		client:           NewClient(baseURL, token),
		wsClient:         NewWebSocketClient(baseURL, token),
		redisClient:      redisClient,
		enabled:          false,
		websocketEnabled: enableWebSocket,
	}

	// Initialize entity cache maps
	i.entityCache.tempSensorToZone = make(map[string]string)
	i.entityCache.valveToZone = make(map[string]string)
	i.entityCache.climateToZone = make(map[string]string)

	return i
}

// Start initializes the Home Assistant integration
func (i *Integration) Start() error {
	if i.enabled {
		return fmt.Errorf("integration already started")
	}

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := i.client.Ping(ctx); err != nil {
		return fmt.Errorf("failed to connect to Home Assistant: %w", err)
	}

	logger.Info("Home Assistant API connection successful")

	// Build entity cache for fast lookups
	if err := i.buildEntityCache(ctx); err != nil {
		logger.Warn("Failed to build entity cache: %v", err)
	}

	// Start WebSocket if enabled
	if i.websocketEnabled {
		if err := i.startWebSocket(); err != nil {
			return fmt.Errorf("failed to start websocket: %w", err)
		}
	}

	i.enabled = true
	logger.Info("Home Assistant integration started")

	return nil
}

// startWebSocket initializes the WebSocket connection
func (i *Integration) startWebSocket() error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := i.wsClient.Connect(ctx); err != nil {
		return err
	}

	// Subscribe to state changes
	_, err := i.wsClient.SubscribeToStateChanges(i.handleStateChange)
	if err != nil {
		return fmt.Errorf("failed to subscribe to state changes: %w", err)
	}

	logger.Info("WebSocket connection established and subscribed to state changes")

	return nil
}

// buildEntityCache builds the entity ID to zone key mapping cache
func (i *Integration) buildEntityCache(ctx context.Context) error {
	i.entityCache.Lock()
	defer i.entityCache.Unlock()

	// Clear existing cache
	i.entityCache.tempSensorToZone = make(map[string]string)
	i.entityCache.valveToZone = make(map[string]string)
	i.entityCache.climateToZone = make(map[string]string)
	i.entityCache.mainClimateID = ""

	// Get all zones
	zoneKeys, err := i.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return fmt.Errorf("failed to get zone keys: %w", err)
	}

	// Build cache from zone data
	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		if tempSensor, ok := zoneData["temperature_sensor_entity_id"]; ok && tempSensor != "" {
			i.entityCache.tempSensorToZone[tempSensor] = key
		}

		if valve, ok := zoneData["valve_switch_entity_id"]; ok && valve != "" {
			i.entityCache.valveToZone[valve] = key
		}

		if climate, ok := zoneData["climate_entity_id"]; ok && climate != "" {
			i.entityCache.climateToZone[climate] = key
		}
	}

	// Get main climate entity ID
	configData, err := i.redisClient.HGetAll(ctx, "multizone:config")
	if err == nil {
		if mainID, ok := configData["main_climate_entity_id"]; ok {
			i.entityCache.mainClimateID = mainID
		}
	}

	logger.Info("Entity cache built: %d temperature sensors, %d valves, %d climate entities",
		len(i.entityCache.tempSensorToZone), len(i.entityCache.valveToZone), len(i.entityCache.climateToZone))

	return nil
}

// RefreshEntityCache refreshes the entity cache (call after zone configuration changes)
func (i *Integration) RefreshEntityCache(ctx context.Context) error {
	return i.buildEntityCache(ctx)
}

// handleStateChange processes state change events from Home Assistant
func (i *Integration) handleStateChange(event *Event) {
	if event.Data == nil {
		return
	}

	// Extract entity_id, new_state, and old_state
	entityID, ok := event.Data["entity_id"].(string)
	if !ok {
		return
	}

	newStateData, ok := event.Data["new_state"].(map[string]interface{})
	if !ok {
		return
	}

	state, ok := newStateData["state"].(string)
	if !ok {
		return
	}

	attributes, _ := newStateData["attributes"].(map[string]interface{})

	logger.Debug("State changed: %s -> %s", entityID, state)

	// Update Redis based on entity type
	ctx := context.Background()

	// Check if this is a temperature sensor
	if i.isTemperatureSensor(entityID, attributes) {
		if err := i.updateTemperatureSensor(ctx, entityID, state, attributes); err != nil {
			logger.Error("Error updating temperature sensor: %v", err)
		}
	}

	// Check if this is a valve switch
	if i.isValveSwitch(entityID) {
		if err := i.updateValveSwitch(ctx, entityID, state); err != nil {
			logger.Error("Error updating valve switch: %v", err)
		}
	}

	// Check if this is the main climate entity
	if i.isMainClimate(entityID) {
		if err := i.updateMainClimate(ctx, entityID, state, attributes); err != nil {
			logger.Error("Error updating main climate: %v", err)
		}
	}

	// Check if this is a zone climate entity
	if i.isZoneClimate(entityID) {
		if err := i.updateZoneClimate(ctx, entityID, state, attributes); err != nil {
			logger.Error("Error updating zone climate: %v", err)
		}
	}
}

// isTemperatureSensor checks if an entity is a temperature sensor
func (i *Integration) isTemperatureSensor(entityID string, attributes map[string]interface{}) bool {
	// Check if entity has device_class: temperature or unit_of_measurement: °C/°F
	if deviceClass, ok := attributes["device_class"].(string); ok && deviceClass == "temperature" {
		return true
	}

	if unit, ok := attributes["unit_of_measurement"].(string); ok {
		return unit == "°C" || unit == "°F" || unit == "C" || unit == "F"
	}

	return false
}

// isValveSwitch checks if an entity is a valve switch using the cache
func (i *Integration) isValveSwitch(entityID string) bool {
	i.entityCache.RLock()
	defer i.entityCache.RUnlock()

	_, exists := i.entityCache.valveToZone[entityID]
	return exists
}

// isMainClimate checks if an entity is the main climate entity using the cache
func (i *Integration) isMainClimate(entityID string) bool {
	i.entityCache.RLock()
	defer i.entityCache.RUnlock()

	return i.entityCache.mainClimateID == entityID
}

// isZoneClimate checks if an entity is a zone climate entity using the cache
func (i *Integration) isZoneClimate(entityID string) bool {
	i.entityCache.RLock()
	defer i.entityCache.RUnlock()

	_, exists := i.entityCache.climateToZone[entityID]
	return exists
}

// updateTemperatureSensor updates temperature sensor data in Redis using cache
func (i *Integration) updateTemperatureSensor(ctx context.Context, entityID, state string, attributes map[string]interface{}) error {
	// Parse temperature value
	temp, err := strconv.ParseFloat(state, 64)
	if err != nil {
		return fmt.Errorf("invalid temperature value: %s", state)
	}

	// Use cache for O(1) lookup
	i.entityCache.RLock()
	zoneKey, exists := i.entityCache.tempSensorToZone[entityID]
	i.entityCache.RUnlock()

	if !exists {
		// Entity not in cache, might be newly added - log for troubleshooting
		logger.Debug("Temperature sensor %s not found in entity cache", entityID)
		return nil
	}

	// Update the zone's current temperature
	if err := i.redisClient.HSet(ctx, zoneKey, "current_temperature", temp); err != nil {
		return err
	}

	logger.Debug("Updated zone temperature: %s -> %.2f°C", zoneKey, temp)

	// Trigger recalculation job
	if err := i.triggerRecalculation(ctx); err != nil {
		logger.Error("Error triggering recalculation: %v", err)
	}

	return nil
}

// updateValveSwitch updates valve switch state in Redis using cache
func (i *Integration) updateValveSwitch(ctx context.Context, entityID, state string) error {
	// Use cache for O(1) lookup
	i.entityCache.RLock()
	zoneKey, exists := i.entityCache.valveToZone[entityID]
	i.entityCache.RUnlock()

	if !exists {
		// Entity not in cache, might be newly added - log for troubleshooting
		logger.Debug("Valve switch %s not found in entity cache", entityID)
		return nil
	}

	// Map HA state to valve state
	valveState := "closed"
	if state == "on" {
		valveState = "open"
	}

	// Update the zone's valve state
	if err := i.redisClient.HSet(ctx, zoneKey, "valve_state", valveState); err != nil {
		return err
	}

	logger.Debug("Updated valve state: %s -> %s", zoneKey, valveState)

	return nil
}

// updateMainClimate updates main climate entity data in Redis
func (i *Integration) updateMainClimate(ctx context.Context, entityID, state string, attributes map[string]interface{}) error {
	updates := make(map[string]interface{})
	updates["hvac_mode"] = state

	// Extract useful attributes
	if currentTemp, ok := attributes["current_temperature"].(float64); ok {
		updates["current_temperature"] = currentTemp
	}

	if targetTemp, ok := attributes["temperature"].(float64); ok {
		updates["target_temperature"] = targetTemp
	}

	if hvacAction, ok := attributes["hvac_action"].(string); ok {
		updates["hvac_action"] = hvacAction
	}

	// Update Redis
	if err := i.redisClient.HSet(ctx, "multizone:main_climate", updates); err != nil {
		return err
	}

	logger.Debug("Updated main climate: %s", entityID)

	return nil
}

// updateZoneClimate updates zone climate entity data in Redis
func (i *Integration) updateZoneClimate(ctx context.Context, entityID, state string, attributes map[string]interface{}) error {
	// Use cache for O(1) lookup
	i.entityCache.RLock()
	zoneKey, exists := i.entityCache.climateToZone[entityID]
	i.entityCache.RUnlock()

	if !exists {
		// Entity not in cache, might be newly added - log for troubleshooting
		logger.Debug("Climate entity %s not found in entity cache", entityID)
		return nil
	}

	// Get zone data to check if temperature sensor is configured
	zoneData, err := i.redisClient.HGetAll(ctx, zoneKey)
	if err != nil {
		return err
	}

	// Extract current temperature from climate entity if no temperature sensor is configured
	tempSensorEntity, hasTempSensor := zoneData["temperature_sensor_entity_id"]
	if (!hasTempSensor || tempSensorEntity == "") {
		if currentTemp, ok := attributes["current_temperature"].(float64); ok {
			// Update zone current temperature from climate entity
			if err := i.redisClient.HSet(ctx, zoneKey, "current_temperature", currentTemp); err != nil {
				return err
			}
			logger.Debug("Updated zone current temperature from HA climate: %s -> %.1f°C", zoneKey, currentTemp)
		}
	}

	// Extract target temperature from climate entity
	if targetTemp, ok := attributes["temperature"].(float64); ok {
		currentTargetStr, ok := zoneData["target_temperature"]
		if !ok {
			currentTargetStr = "0"
		}

		currentTarget, err := strconv.ParseFloat(currentTargetStr, 64)
		if err != nil {
			currentTarget = 0
		}

		// Only update if the temperature changed (to avoid loops)
		// Use threshold from default configuration for consistency
		if math.Abs(targetTemp-currentTarget) > models.DefaultTargetChangeThreshold {
			// Update zone target temperature
			if err := i.redisClient.HSet(ctx, zoneKey, "target_temperature", targetTemp); err != nil {
				return err
			}

			logger.Info("Updated zone target temperature from HA climate: %s -> %.1f°C", zoneKey, targetTemp)

			// Trigger recalculation job
			if err := i.triggerRecalculation(ctx); err != nil {
				logger.Error("Error triggering recalculation: %v", err)
			}
		}
	}

	logger.Debug("Updated zone climate: %s -> %s", zoneKey, entityID)

	return nil
}

// triggerRecalculation adds a calculation job to the queue
func (i *Integration) triggerRecalculation(ctx context.Context) error {
	job := map[string]interface{}{
		"id":        fmt.Sprintf("calc_%d", time.Now().UnixNano()),
		"type":      "calculate_temp",
		"timestamp": time.Now().Format(time.RFC3339),
	}

	jobJSON, err := json.Marshal(job)
	if err != nil {
		return err
	}

	return i.redisClient.LPush(ctx, "multizone:job_queue", string(jobJSON))
}

// SyncAllStates synchronizes all entity states from Home Assistant to Redis
func (i *Integration) SyncAllStates(ctx context.Context) error {
	if !i.enabled {
		return fmt.Errorf("integration not started")
	}

	// Get all zones
	zoneKeys, err := i.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return err
	}

	logger.Info("Syncing states for %d zones", len(zoneKeys))

	// Sync each zone's sensors and climate entities
	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		// Sync climate entity first (if configured)
		climateEntity, hasClimateEntity := zoneData["climate_entity_id"]
		if hasClimateEntity && climateEntity != "" {
			if err := i.syncZoneClimate(ctx, key, climateEntity); err != nil {
				logger.Error("Error syncing zone climate entity %s: %v", climateEntity, err)
			}
		}

		// Sync temperature sensor (overrides climate entity current temp if present)
		if sensorEntity, ok := zoneData["temperature_sensor_entity_id"]; ok && sensorEntity != "" {
			if err := i.syncTemperatureSensor(ctx, key, sensorEntity); err != nil {
				logger.Error("Error syncing temperature sensor %s: %v", sensorEntity, err)
			}
		}

		// Sync valve switch
		if valveEntity, ok := zoneData["valve_switch_entity_id"]; ok && valveEntity != "" {
			if err := i.syncValveSwitch(ctx, key, valveEntity); err != nil {
				logger.Error("Error syncing valve switch %s: %v", valveEntity, err)
			}
		}
	}

	// Sync main climate
	configData, err := i.redisClient.HGetAll(ctx, "multizone:config")
	if err == nil {
		if mainEntity, ok := configData["main_climate_entity_id"]; ok && mainEntity != "" {
			if err := i.syncMainClimate(ctx, mainEntity); err != nil {
				logger.Error("Error syncing main climate %s: %v", mainEntity, err)
			}
		}
	}

	logger.Info("State synchronization complete")

	return nil
}

// syncTemperatureSensor syncs a temperature sensor from HA to Redis
func (i *Integration) syncTemperatureSensor(ctx context.Context, zoneKey, entityID string) error {
	state, err := i.client.GetState(ctx, entityID)
	if err != nil {
		return err
	}

	temp, err := strconv.ParseFloat(state.State, 64)
	if err != nil {
		return err
	}

	return i.redisClient.HSet(ctx, zoneKey, "current_temperature", temp)
}

// syncValveSwitch syncs a valve switch from HA to Redis
func (i *Integration) syncValveSwitch(ctx context.Context, zoneKey, entityID string) error {
	state, err := i.client.GetState(ctx, entityID)
	if err != nil {
		return err
	}

	valveState := "closed"
	if state.State == "on" {
		valveState = "open"
	}

	return i.redisClient.HSet(ctx, zoneKey, "valve_state", valveState)
}

// syncZoneClimate syncs a zone climate entity from HA to Redis
func (i *Integration) syncZoneClimate(ctx context.Context, zoneKey, entityID string) error {
	state, err := i.client.GetState(ctx, entityID)
	if err != nil {
		return err
	}

	updates := make(map[string]interface{})

	// Get zone data to check if temperature sensor is configured
	zoneData, err := i.redisClient.HGetAll(ctx, zoneKey)
	if err != nil {
		return err
	}

	// Sync current temperature from climate entity if no temperature sensor is configured
	tempSensorEntity, hasTempSensor := zoneData["temperature_sensor_entity_id"]
	if (!hasTempSensor || tempSensorEntity == "") {
		if currentTemp, ok := state.Attributes["current_temperature"].(float64); ok {
			updates["current_temperature"] = currentTemp
			logger.Debug("Synced current temperature from zone climate entity: %.1f", currentTemp)
		}
	}

	// Sync target temperature from climate entity
	if targetTemp, ok := state.Attributes["temperature"].(float64); ok {
		updates["target_temperature"] = targetTemp
		logger.Debug("Synced target temperature from zone climate entity: %.1f", targetTemp)
	}

	if len(updates) > 0 {
		return i.redisClient.HSet(ctx, zoneKey, updates)
	}

	return nil
}

// syncMainClimate syncs the main climate entity from HA to Redis
func (i *Integration) syncMainClimate(ctx context.Context, entityID string) error {
	state, err := i.client.GetState(ctx, entityID)
	if err != nil {
		return err
	}

	updates := map[string]interface{}{
		"hvac_mode": state.State,
	}

	if currentTemp, ok := state.Attributes["current_temperature"].(float64); ok {
		updates["current_temperature"] = currentTemp
	}

	if targetTemp, ok := state.Attributes["temperature"].(float64); ok {
		updates["target_temperature"] = targetTemp
	}

	if hvacAction, ok := state.Attributes["hvac_action"].(string); ok {
		updates["hvac_action"] = hvacAction
	}

	return i.redisClient.HSet(ctx, "multizone:main_climate", updates)
}

// SetValveState sets the state of a valve in Home Assistant
func (i *Integration) SetValveState(ctx context.Context, entityID string, open bool) error {
	if !i.enabled {
		return fmt.Errorf("integration not started")
	}

	if open {
		return i.client.TurnOnSwitch(ctx, entityID)
	}
	return i.client.TurnOffSwitch(ctx, entityID)
}

// SetMainTemperature sets the main climate temperature in Home Assistant
func (i *Integration) SetMainTemperature(ctx context.Context, entityID string, temperature float64) error {
	if !i.enabled {
		return fmt.Errorf("integration not started")
	}

	return i.client.SetTemperature(ctx, entityID, temperature)
}

// SetZoneClimateTemperature sets a zone climate entity temperature in Home Assistant
func (i *Integration) SetZoneClimateTemperature(ctx context.Context, zoneKey string) error {
	if !i.enabled {
		return fmt.Errorf("integration not started")
	}

	// Get zone data to find climate entity and target temperature
	zoneData, err := i.redisClient.HGetAll(ctx, zoneKey)
	if err != nil {
		return err
	}

	climateEntityID, ok := zoneData["climate_entity_id"]
	if !ok || climateEntityID == "" {
		// No climate entity configured for this zone
		return nil
	}

	targetTempStr, ok := zoneData["target_temperature"]
	if !ok {
		return nil
	}

	targetTemp, err := strconv.ParseFloat(targetTempStr, 64)
	if err != nil {
		return err
	}

	// Set temperature on the zone's climate entity
	if err := i.client.SetTemperature(ctx, climateEntityID, targetTemp); err != nil {
		return err
	}

	logger.Info("Set zone climate temperature: %s (%s) -> %.1f°C", zoneKey, climateEntityID, targetTemp)

	return nil
}

// Stop stops the Home Assistant integration
func (i *Integration) Stop() error {
	if !i.enabled {
		return nil
	}

	if i.websocketEnabled && i.wsClient.IsConnected() {
		if err := i.wsClient.Close(); err != nil {
			logger.Error("Error closing websocket: %v", err)
		}
	}

	i.enabled = false

	logger.Info("Home Assistant integration stopped")

	return nil
}

// IsEnabled returns whether the integration is enabled
func (i *Integration) IsEnabled() bool {
	return i.enabled
}

// GetClient returns the underlying HTTP client
func (i *Integration) GetClient() *Client {
	return i.client
}

// GetWebSocketClient returns the underlying WebSocket client
func (i *Integration) GetWebSocketClient() *WebSocketClient {
	return i.wsClient
}
