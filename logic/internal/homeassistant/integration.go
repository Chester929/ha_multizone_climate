package homeassistant

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
)

// Integration manages the Home Assistant integration
type Integration struct {
	client           *Client
	wsClient         *WebSocketClient
	redisClient      *redis.Client
	enabled          bool
	websocketEnabled bool
	ctx              context.Context
	cancel           context.CancelFunc
}

// NewIntegration creates a new Home Assistant integration
func NewIntegration(baseURL, token string, redisClient *redis.Client, enableWebSocket bool) *Integration {
	ctx, cancel := context.WithCancel(context.Background())

	return &Integration{
		client:           NewClient(baseURL, token),
		wsClient:         NewWebSocketClient(baseURL, token),
		redisClient:      redisClient,
		enabled:          false,
		websocketEnabled: enableWebSocket,
		ctx:              ctx,
		cancel:           cancel,
	}
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

	log.Println("Home Assistant API connection successful")

	// Start WebSocket if enabled
	if i.websocketEnabled {
		if err := i.startWebSocket(); err != nil {
			return fmt.Errorf("failed to start websocket: %w", err)
		}
	}

	i.enabled = true
	log.Println("Home Assistant integration started")

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

	log.Println("WebSocket connection established and subscribed to state changes")

	return nil
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

	log.Printf("State changed: %s -> %s", entityID, state)

	// Update Redis based on entity type
	ctx := context.Background()

	// Check if this is a temperature sensor
	if i.isTemperatureSensor(entityID, attributes) {
		if err := i.updateTemperatureSensor(ctx, entityID, state, attributes); err != nil {
			log.Printf("Error updating temperature sensor: %v", err)
		}
	}

	// Check if this is a valve switch
	if i.isValveSwitch(entityID) {
		if err := i.updateValveSwitch(ctx, entityID, state); err != nil {
			log.Printf("Error updating valve switch: %v", err)
		}
	}

	// Check if this is the main climate entity
	if i.isMainClimate(entityID) {
		if err := i.updateMainClimate(ctx, entityID, state, attributes); err != nil {
			log.Printf("Error updating main climate: %v", err)
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

// isValveSwitch checks if an entity is a valve switch
func (i *Integration) isValveSwitch(entityID string) bool {
	// Check all zones to see if this entity is configured as a valve
	ctx := context.Background()
	zoneKeys, err := i.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return false
	}

	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		if valveEntity, ok := zoneData["valve_switch_entity_id"]; ok && valveEntity == entityID {
			return true
		}
	}

	return false
}

// isMainClimate checks if an entity is the main climate entity
func (i *Integration) isMainClimate(entityID string) bool {
	ctx := context.Background()
	configData, err := i.redisClient.HGetAll(ctx, "multizone:config")
	if err != nil {
		return false
	}

	mainEntityID, ok := configData["main_climate_entity_id"]
	return ok && mainEntityID == entityID
}

// updateTemperatureSensor updates temperature sensor data in Redis
func (i *Integration) updateTemperatureSensor(ctx context.Context, entityID, state string, attributes map[string]interface{}) error {
	// Parse temperature value
	temp, err := strconv.ParseFloat(state, 64)
	if err != nil {
		return fmt.Errorf("invalid temperature value: %s", state)
	}

	// Find which zone uses this sensor
	zoneKeys, err := i.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return err
	}

	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		sensorEntity, ok := zoneData["temperature_sensor_entity_id"]
		if !ok || sensorEntity != entityID {
			continue
		}

		// Update the zone's current temperature
		if err := i.redisClient.HSet(ctx, key, "current_temperature", temp); err != nil {
			return err
		}

		log.Printf("Updated zone temperature: %s -> %.2f°C", key, temp)

		// Trigger recalculation job
		if err := i.triggerRecalculation(ctx); err != nil {
			log.Printf("Error triggering recalculation: %v", err)
		}

		break
	}

	return nil
}

// updateValveSwitch updates valve switch state in Redis
func (i *Integration) updateValveSwitch(ctx context.Context, entityID, state string) error {
	// Find which zone uses this valve
	zoneKeys, err := i.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return err
	}

	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		valveEntity, ok := zoneData["valve_switch_entity_id"]
		if !ok || valveEntity != entityID {
			continue
		}

		// Map HA state to valve state
		valveState := "closed"
		if state == "on" {
			valveState = "open"
		}

		// Update the zone's valve state
		if err := i.redisClient.HSet(ctx, key, "valve_state", valveState); err != nil {
			return err
		}

		log.Printf("Updated valve state: %s -> %s", key, valveState)
		break
	}

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

	log.Printf("Updated main climate: %s", entityID)

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

	log.Printf("Syncing states for %d zones", len(zoneKeys))

	// Sync each zone's sensors
	for _, key := range zoneKeys {
		zoneData, err := i.redisClient.HGetAll(ctx, key)
		if err != nil {
			continue
		}

		// Sync temperature sensor
		if sensorEntity, ok := zoneData["temperature_sensor_entity_id"]; ok && sensorEntity != "" {
			if err := i.syncTemperatureSensor(ctx, key, sensorEntity); err != nil {
				log.Printf("Error syncing temperature sensor %s: %v", sensorEntity, err)
			}
		}

		// Sync valve switch
		if valveEntity, ok := zoneData["valve_switch_entity_id"]; ok && valveEntity != "" {
			if err := i.syncValveSwitch(ctx, key, valveEntity); err != nil {
				log.Printf("Error syncing valve switch %s: %v", valveEntity, err)
			}
		}
	}

	// Sync main climate
	configData, err := i.redisClient.HGetAll(ctx, "multizone:config")
	if err == nil {
		if mainEntity, ok := configData["main_climate_entity_id"]; ok && mainEntity != "" {
			if err := i.syncMainClimate(ctx, mainEntity); err != nil {
				log.Printf("Error syncing main climate %s: %v", mainEntity, err)
			}
		}
	}

	log.Println("State synchronization complete")

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

// Stop stops the Home Assistant integration
func (i *Integration) Stop() error {
	if !i.enabled {
		return nil
	}

	if i.websocketEnabled && i.wsClient.IsConnected() {
		if err := i.wsClient.Close(); err != nil {
			log.Printf("Error closing websocket: %v", err)
		}
	}

	i.cancel()
	i.enabled = false

	log.Println("Home Assistant integration stopped")

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
