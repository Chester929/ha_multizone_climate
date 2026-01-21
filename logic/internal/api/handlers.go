package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/algorithm"
	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/chester929/ha_multizone_climate/logic/internal/statistics"
	"github.com/gorilla/mux"
)

const (
	// entityIDPattern validates Home Assistant entity IDs (domain.entity_name)
	entityIDPatternString = `^[a-z_]+\.[a-z0-9_]+$`

	// zoneIDPattern validates zone IDs (alphanumeric with underscores and hyphens)
	zoneIDPatternString = `^[a-zA-Z0-9_-]+$`

	// maxStatisticsHours defines the maximum number of hours that can be requested
	// for statistics queries to prevent abuse and performance issues (30 days)
	maxStatisticsHours = 720
)

// entityIDPattern is compiled once at package initialization
var entityIDPattern = regexp.MustCompile(entityIDPatternString)

// zoneIDPattern is compiled once at package initialization
var zoneIDPattern = regexp.MustCompile(zoneIDPatternString)

// HealthHandler returns the health status of the service
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "healthy",
		"time":   time.Now().Format(time.RFC3339),
	})
}

// StatusHandler returns the status of the system
func StatusHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.Background()

		// Check Redis connection
		err := client.Ping(ctx)
		redisStatus := "connected"
		if err != nil {
			redisStatus = "disconnected"
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "running",
			"redis":  redisStatus,
			"time":   time.Now().Format(time.RFC3339),
		})
	}
}

// MetricsHandler returns system metrics
func MetricsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.Background()

		// Get zone count
		zoneKeys, _ := client.Keys(ctx, "multizone:zone:*")

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"zones_count": len(zoneKeys),
			"time":        time.Now().Format(time.RFC3339),
		})
	}
}

// ListZonesHandler returns all zones
func ListZonesHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.Background()

		// Get all zone keys
		zoneKeys, err := client.Keys(ctx, "multizone:zone:*")
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		zones := []map[string]interface{}{}
		for _, key := range zoneKeys {
			zoneData, err := client.HGetAll(ctx, key)
			if err != nil {
				continue
			}

			// Return all zone data as-is from Redis
			zones = append(zones, convertToInterfaceMap(zoneData))
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(zones)
	}
}

// convertToInterfaceMap converts a map[string]string to map[string]interface{}
func convertToInterfaceMap(data map[string]string) map[string]interface{} {
	result := make(map[string]interface{})
	for k, v := range data {
		result[k] = v
	}
	return result
}

// GetZoneHandler returns a specific zone
func GetZoneHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		ctx := context.Background()
		key := "multizone:zone:" + zoneID

		zoneData, err := client.HGetAll(ctx, key)
		if err != nil || len(zoneData) == 0 {
			http.Error(w, "Zone not found", http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(zoneData)
	}
}

// CreateZoneHandler creates a new zone
func CreateZoneHandler(client *redis.Client, integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var zone map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&zone); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Invalid JSON format",
			})
			return
		}

		ctx := context.Background()

		// Validate required fields
		name, nameOk := zone["name"].(string)
		if !nameOk || name == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Zone name is required",
			})
			return
		}

		// Generate zone ID if not provided
		zoneID, idOk := zone["id"].(string)
		if !idOk || zoneID == "" {
			zoneID = "zone-" + strconv.FormatInt(time.Now().UnixNano()/1000000, 10)
		}

		// Validate zone ID format
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Zone ID must contain only alphanumeric characters, hyphens, and underscores",
			})
			return
		}

		// Check if zone already exists
		key := "multizone:zone:" + zoneID
		exists, err := client.Exists(ctx, key)
		if err != nil {
			logger.Error("Failed to check zone existence: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to check zone existence",
			})
			return
		}
		if exists > 0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Zone with this ID already exists",
			})
			return
		}

		// Validate temperature sensor entity if provided
		if tempSensor, ok := zone["temperature_sensor_entity_id"].(string); ok && tempSensor != "" {
			if !entityIDPattern.MatchString(tempSensor) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid temperature sensor entity ID format, expected format: domain.entity_name",
				})
				return
			}
		}

		// Validate valve switch entity if provided
		if valveSwitch, ok := zone["valve_switch_entity_id"].(string); ok && valveSwitch != "" {
			if !entityIDPattern.MatchString(valveSwitch) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid valve switch entity ID format, expected format: domain.entity_name",
				})
				return
			}
		}

		// Validate climate entity if provided
		climateEntityID := ""
		if climateEntity, ok := zone["climate_entity_id"].(string); ok && climateEntity != "" {
			if !entityIDPattern.MatchString(climateEntity) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid climate entity ID format, expected format: domain.entity_name",
				})
				return
			}
			climateEntityID = climateEntity
		}

		// Validate target temperature if provided
		if targetTemp, ok := zone["target_temperature"].(string); ok && targetTemp != "" {
			if err := validateTemperature(targetTemp, "Target temperature"); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": err.Error(),
				})
				return
			}
		}

		// Validate priority if provided
		if priority, ok := zone["priority"].(string); ok && priority != "" {
			if err := validatePriority(priority); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": err.Error(),
				})
				return
			}
		}

		// Auto-load data from climate entity if HA integration is enabled
		if climateEntityID != "" && integration != nil && integration.IsEnabled() {
			haClient := integration.GetClient()
			climateState, err := haClient.GetState(ctx, climateEntityID)
			if err != nil {
				logger.Warn("Failed to load climate entity state: %v", err)
			} else {
				// Auto-load current temperature if not explicitly overridden by temperature sensor
				if _, hasTempSensor := zone["temperature_sensor_entity_id"]; !hasTempSensor {
					if currentTemp, ok := climateState.Attributes["current_temperature"].(float64); ok {
						zone["current_temperature"] = fmt.Sprintf("%.1f", currentTemp)
						logger.Info("Auto-loaded current temperature from climate entity: %.1f", currentTemp)
					}
				}
				
				// Auto-load target temperature if not provided
				if _, hasTargetTemp := zone["target_temperature"]; !hasTargetTemp {
					if targetTemp, ok := climateState.Attributes["temperature"].(float64); ok {
						zone["target_temperature"] = fmt.Sprintf("%.1f", targetTemp)
						logger.Info("Auto-loaded target temperature from climate entity: %.1f", targetTemp)
					}
				}
			}
		}

		// Set defaults for missing fields
		zoneData := map[string]interface{}{
			"id":                           zoneID,
			"name":                         name,
			"enabled":                      getStringOrDefault(zone, "enabled", "true"),
			"target_temperature":           getStringOrDefault(zone, "target_temperature", "20"),
			"current_temperature":          getStringOrDefault(zone, "current_temperature", "N/A"),
			"satisfaction":                 getStringOrDefault(zone, "satisfaction", "unknown"),
			"valve_state":                  getStringOrDefault(zone, "valve_state", "closed"),
			"priority":                     getStringOrDefault(zone, "priority", "0"),
			"temperature_sensor_entity_id": getStringOrDefault(zone, "temperature_sensor_entity_id", ""),
			"valve_switch_entity_id":       getStringOrDefault(zone, "valve_switch_entity_id", ""),
			"climate_entity_id":            getStringOrDefault(zone, "climate_entity_id", ""),
		}

		// Save zone to Redis
		if err := client.HSet(ctx, key, zoneData); err != nil {
			logger.Error("Failed to create zone: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to create zone",
			})
			return
		}

		// Refresh entity cache after zone creation
		if integration != nil && integration.IsEnabled() {
			if err := integration.RefreshEntityCache(ctx); err != nil {
				logger.Error("Failed to refresh entity cache: %v", err)
			}
		}

		// If zone has temperature sensor, sync current temperature from HA
		if tempSensorEntity := getStringOrDefault(zone, "temperature_sensor_entity_id", ""); tempSensorEntity != "" && integration != nil && integration.IsEnabled() {
			haClient := integration.GetClient()
			sensorState, err := haClient.GetState(ctx, tempSensorEntity)
			if err != nil {
				logger.Warn("Failed to sync temperature sensor: %v", err)
			} else {
				temp, err := strconv.ParseFloat(sensorState.State, 64)
				if err == nil {
					client.HSet(ctx, key, "current_temperature", fmt.Sprintf("%.1f", temp))
					logger.Info("Synced current temperature from sensor: %.1f", temp)
				}
			}
		}

		logger.Info("Zone created successfully: %s (%s)", zoneID, name)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "created",
			"id":     zoneID,
		})
	}
}

// UpdateZoneHandler updates a zone
func UpdateZoneHandler(client *redis.Client, integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID format
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Invalid zone ID format",
			})
			return
		}

		var updates map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		ctx := context.Background()
		key := "multizone:zone:" + zoneID

		// Check if zone exists
		exists, err := client.Exists(ctx, key)
		if err != nil {
			logger.Error("Failed to check zone existence: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to check zone existence",
			})
			return
		}
		if exists == 0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Zone not found",
			})
			return
		}

		// Validate entity IDs if provided
		if tempSensor, ok := updates["temperature_sensor_entity_id"].(string); ok && tempSensor != "" {
			if !entityIDPattern.MatchString(tempSensor) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid temperature sensor entity ID format",
				})
				return
			}
		}

		if valveSwitch, ok := updates["valve_switch_entity_id"].(string); ok && valveSwitch != "" {
			if !entityIDPattern.MatchString(valveSwitch) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid valve switch entity ID format",
				})
				return
			}
		}

		if climateEntity, ok := updates["climate_entity_id"].(string); ok && climateEntity != "" {
			if !entityIDPattern.MatchString(climateEntity) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid climate entity ID format",
				})
				return
			}
		}

		// Track if target temperature is being updated
		targetTempUpdated := false
		if _, ok := updates["target_temperature"]; ok {
			targetTempUpdated = true
		}

		// Track if entity IDs are being updated (need cache refresh)
		entityIDsUpdated := false
		if _, ok := updates["temperature_sensor_entity_id"]; ok {
			entityIDsUpdated = true
		}
		if _, ok := updates["valve_switch_entity_id"]; ok {
			entityIDsUpdated = true
		}
		if _, ok := updates["climate_entity_id"]; ok {
			entityIDsUpdated = true
		}

		// Validate target temperature if provided
		if targetTemp, ok := updates["target_temperature"].(string); ok && targetTemp != "" {
			if err := validateTemperature(targetTemp, "Target temperature"); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": err.Error(),
				})
				return
			}
		}

		// Validate priority if provided
		if priority, ok := updates["priority"].(string); ok && priority != "" {
			if err := validatePriority(priority); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": err.Error(),
				})
				return
			}
		}

		// Update zone in Redis
		if err := client.HSet(ctx, key, updates); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		// If entity IDs changed, refresh the entity cache
		if entityIDsUpdated && integration != nil && integration.IsEnabled() {
			if err := integration.RefreshEntityCache(ctx); err != nil {
				logger.Error("Failed to refresh entity cache: %v", err)
			} else {
				logger.Info("Entity cache refreshed after zone update")
			}
		}

		// If target temperature changed, update the zone's climate entity in HA
		if targetTempUpdated && integration != nil && integration.IsEnabled() {
			if err := integration.SetZoneClimateTemperature(ctx, key); err != nil {
				logger.Error("Failed to set zone climate temperature: %v", err)
				// Don't fail the request if HA update fails
			}
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
	}
}

// DeleteZoneHandler deletes a zone
func DeleteZoneHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID format
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Invalid zone ID format",
			})
			return
		}

		ctx := context.Background()
		key := "multizone:zone:" + zoneID

		// Check if zone exists
		exists, err := client.Exists(ctx, key)
		if err != nil {
			logger.Error("Failed to check zone existence: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to check zone existence",
			})
			return
		}
		if exists == 0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Zone not found",
			})
			return
		}

		// Delete zone and its history
		if err := client.Del(ctx, key); err != nil {
			logger.Error("Failed to delete zone: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to delete zone",
			})
			return
		}

		// Also delete zone history
		historyKey := "multizone:history:zone:" + zoneID
		client.Del(ctx, historyKey) // Ignore error as history might not exist

		logger.Info("Zone deleted successfully: %s", zoneID)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
	}
}

// Helper function to get string value from map or return default
func getStringOrDefault(m map[string]interface{}, key string, defaultValue string) string {
	if val, ok := m[key].(string); ok {
		return val
	}
	return defaultValue
}

// Helper function to validate temperature range
func validateTemperature(tempStr string, fieldName string) error {
	temp, err := strconv.ParseFloat(tempStr, 64)
	if err != nil || temp < -50 || temp > 100 {
		return fmt.Errorf("%s must be between -50 and 100", fieldName)
	}
	return nil
}

// Helper function to validate priority range
func validatePriority(priorityStr string) error {
	priority, err := strconv.Atoi(priorityStr)
	if err != nil || priority < 0 || priority > 100 {
		return fmt.Errorf("priority must be between 0 and 100")
	}
	return nil
}

// CalculateMainTempHandler triggers main temperature calculation
func CalculateMainTempHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: Implement actual temperature calculation logic
		// In a full implementation, this would:
		// 1. Load all zones from Redis
		// 2. Load global configuration
		// 3. Call algorithm.CalculateMainTargetTemperature
		// 4. Update Redis with new target
		// 5. Queue valve update job

		// Placeholder response
		result := map[string]interface{}{
			"status":  "calculated",
			"message": "Temperature calculation triggered",
		}

		// Example of using the algorithm (commented out as we need real data)
		_ = algorithm.CalculateMainTargetTemperature

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	}
}

// HAStatusHandler returns the status of Home Assistant integration
func HAStatusHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		status := map[string]interface{}{
			"enabled":   integration.IsEnabled(),
			"websocket": false,
			"time":      time.Now().Format(time.RFC3339),
		}

		if integration.IsEnabled() {
			wsClient := integration.GetWebSocketClient()
			status["websocket"] = wsClient.IsConnected()
		}

		json.NewEncoder(w).Encode(status)
	}
}

// HATestConnectionHandler tests the Home Assistant connection
func HATestConnectionHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		logger.Debug("Received HA test connection request from %s", r.RemoteAddr)
		ctx := r.Context()

		client := integration.GetClient()
		err := client.Ping(ctx)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			logger.Error("HA test connection failed: %v", err)
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"connected": false,
				"error":     err.Error(),
			})
			return
		}

		logger.Info("HA test connection successful")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"connected": true,
			"message":   "Home Assistant connection successful",
		})
	}
}

// HASyncStatesHandler triggers a manual synchronization of all states
func HASyncStatesHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !integration.IsEnabled() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Home Assistant integration is not enabled",
			})
			return
		}

		ctx := r.Context()
		err := integration.SyncAllStates(ctx)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "success",
			"message": "States synchronized successfully",
		})
	}
}

// HASetValveHandler controls a valve via Home Assistant
func HASetValveHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !integration.IsEnabled() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Home Assistant integration is not enabled",
			})
			return
		}

		var req struct {
			EntityID string `json:"entity_id"`
			Open     bool   `json:"open"`
		}

		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		// Validate entity_id format
		if !entityIDPattern.MatchString(req.EntityID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  "invalid entity_id format, expected format: domain.entity_name",
			})
			return
		}

		ctx := r.Context()
		err := integration.SetValveState(ctx, req.EntityID, req.Open)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "success",
			"entity_id": req.EntityID,
			"state":     map[string]bool{"open": req.Open},
		})
	}
}

// HASetMainTempHandler sets the main climate temperature via Home Assistant
func HASetMainTempHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !integration.IsEnabled() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Home Assistant integration is not enabled",
			})
			return
		}

		var req struct {
			EntityID    string  `json:"entity_id"`
			Temperature float64 `json:"temperature"`
		}

		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		// Validate entity_id format
		if !entityIDPattern.MatchString(req.EntityID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  "invalid entity_id format, expected format: domain.entity_name",
			})
			return
		}

		// Validate temperature bounds (reasonable range for HVAC systems)
		if req.Temperature < 5.0 || req.Temperature > 35.0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  "temperature must be between 5°C and 35°C",
			})
			return
		}

		ctx := r.Context()
		err := integration.SetMainTemperature(ctx, req.EntityID, req.Temperature)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":      "success",
			"entity_id":   req.EntityID,
			"temperature": req.Temperature,
		})
	}
}

// HAGetEntitiesHandler retrieves entities from Home Assistant
func HAGetEntitiesHandler(integration *homeassistant.Integration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Check for nil integration
		if integration == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Home Assistant integration is not configured",
			})
			return
		}

		if !integration.IsEnabled() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Home Assistant integration is not enabled",
			})
			return
		}

		ctx := r.Context()

		// Get optional domain filter from query params
		domain := r.URL.Query().Get("domain")

		// Fetch all entity states from Home Assistant
		client := integration.GetClient()
		states, err := client.GetStates(ctx)

		if err != nil {
			logger.Error("Failed to fetch entities from HA: %v", err)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": fmt.Sprintf("Failed to fetch entities: %v", err),
			})
			return
		}

		// Filter and format entities
		entities := make([]map[string]interface{}, 0)
		for _, state := range states {
			// Apply domain filter if specified
			if domain != "" {
				// Extract domain from entity_id (format: domain.entity_name)
				parts := strings.SplitN(state.EntityID, ".", 2)
				if len(parts) < 2 || parts[0] != domain {
					continue
				}
			}

			// Build entity response
			entity := map[string]interface{}{
				"entity_id": state.EntityID,
				"state":     state.State,
			}

			// Add friendly name if available
			if friendlyName, ok := state.Attributes["friendly_name"].(string); ok {
				entity["friendly_name"] = friendlyName
			}

			// For climate entities, include additional attributes
			if strings.HasPrefix(state.EntityID, "climate.") {
				if currentTemp, ok := state.Attributes["current_temperature"]; ok {
					entity["current_temperature"] = currentTemp
				}
				if targetTemp, ok := state.Attributes["temperature"]; ok {
					entity["temperature"] = targetTemp
				}
			}

			entities = append(entities, entity)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"entities": entities,
			"count":    len(entities),
		})
	}
}

// StatisticsTemperatureHistoryHandler returns temperature history for a zone
func StatisticsTemperatureHistoryHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID to prevent injection attacks
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "invalid zone_id format",
			})
			return
		}

		// Get hours parameter (default 24 hours, max 720 hours/30 days)
		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		history, err := tracker.GetTemperatureHistory(ctx, zoneID, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"zone_id": zoneID,
			"hours":   hours,
			"count":   len(history),
			"data":    history,
		})
	}
}

// StatisticsValveActivityHandler returns valve activity history for a zone
func StatisticsValveActivityHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID to prevent injection attacks
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "invalid zone_id format",
			})
			return
		}

		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		activity, err := tracker.GetValveActivityHistory(ctx, zoneID, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"zone_id": zoneID,
			"hours":   hours,
			"count":   len(activity),
			"data":    activity,
		})
	}
}

// StatisticsEnergyMetricsHandler returns energy consumption metrics for a zone
func StatisticsEnergyMetricsHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID to prevent injection attacks
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "invalid zone_id format",
			})
			return
		}

		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		metrics, err := tracker.GetEnergyMetrics(ctx, zoneID, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(metrics)
	}
}

// StatisticsComfortMetricsHandler returns comfort metrics for a zone
func StatisticsComfortMetricsHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		// Validate zone ID to prevent injection attacks
		if !zoneIDPattern.MatchString(zoneID) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "invalid zone_id format",
			})
			return
		}

		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		metrics, err := tracker.GetComfortMetrics(ctx, zoneID, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(metrics)
	}
}

// StatisticsAllZonesComfortHandler returns comfort summary for all zones
func StatisticsAllZonesComfortHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		summary, err := tracker.GetAllZonesComfortSummary(ctx, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"hours": hours,
			"zones": summary,
		})
	}
}

// StatisticsPerformanceMetricsHandler returns system performance metrics
func StatisticsPerformanceMetricsHandler(tracker *statistics.Tracker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hours := 24
		if hoursParam := r.URL.Query().Get("hours"); hoursParam != "" {
			if h, err := strconv.Atoi(hoursParam); err == nil && h > 0 {
				hours = h
				if hours > maxStatisticsHours {
					hours = maxStatisticsHours
				}
			}
		}

		ctx := r.Context()
		metrics, err := tracker.GetSystemPerformanceMetrics(ctx, hours)

		w.Header().Set("Content-Type", "application/json")

		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(metrics)
	}
}

// GetGlobalConfigHandler returns the global configuration
func GetGlobalConfigHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.Background()

		config, err := client.HGetAll(ctx, "multizone:config")
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to fetch configuration",
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(config)
	}
}

// UpdateGlobalConfigHandler updates the global configuration
func UpdateGlobalConfigHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var config map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Invalid JSON format",
			})
			return
		}

		ctx := context.Background()

		// Validate main climate entity ID if provided
		if mainClimateEntity, ok := config["main_climate_entity_id"].(string); ok && mainClimateEntity != "" {
			if !entityIDPattern.MatchString(mainClimateEntity) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid main climate entity ID format, expected format: domain.entity_name",
				})
				return
			}
		}

		// Validate numeric configuration values if provided
		if mainTargetAllZonesSatisfied, ok := config["main_target_all_zones_satisfied"].(string); ok && mainTargetAllZonesSatisfied != "" {
			temp, err := strconv.ParseFloat(mainTargetAllZonesSatisfied, 64)
			if err != nil || temp < 5 || temp > 35 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "main_target_all_zones_satisfied must be between 5 and 35",
				})
				return
			}
		}

		if mainMinTemp, ok := config["main_min_temp"].(string); ok && mainMinTemp != "" {
			temp, err := strconv.ParseFloat(mainMinTemp, 64)
			if err != nil || temp < 5 || temp > 35 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "main_min_temp must be between 5 and 35",
				})
				return
			}
		}

		if mainMaxTemp, ok := config["main_max_temp"].(string); ok && mainMaxTemp != "" {
			temp, err := strconv.ParseFloat(mainMaxTemp, 64)
			if err != nil || temp < 5 || temp > 90 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "main_max_temp must be between 5 and 90",
				})
				return
			}
		}

		// Save configuration to Redis
		if err := client.HSet(ctx, "multizone:config", config); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to update configuration",
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "updated",
		})
	}
}

// GetIntegrationSettingsHandler returns the integration settings
func GetIntegrationSettingsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.Background()

		settings, err := client.HGetAll(ctx, "multizone:integrations")
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to fetch integration settings",
			})
			return
		}

		// Apply defaults for missing values
		if _, ok := settings["ha_websocket"]; !ok || settings["ha_websocket"] == "" {
			settings["ha_websocket"] = "true"
		}

		// Mask sensitive fields
		maskedSettings := make(map[string]interface{})
		for k, v := range settings {
			maskedSettings[k] = v
		}
		if token, ok := maskedSettings["ha_token"].(string); ok && token != "" {
			maskedSettings["ha_token"] = "••••••••"
		}
		if password, ok := maskedSettings["mqtt_password"].(string); ok && password != "" {
			maskedSettings["mqtt_password"] = "••••••••"
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(maskedSettings)
	}
}

// UpdateIntegrationSettingsHandler updates the integration settings
func UpdateIntegrationSettingsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var settings map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&settings); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Invalid JSON format",
			})
			return
		}

		ctx := context.Background()

		// Get existing settings to merge with update
		existingSettings, err := client.HGetAll(ctx, "multizone:integrations")
		if err != nil {
			logger.Warn("Failed to load existing integration settings: %v", err)
			existingSettings = make(map[string]string)
		}

		// Merge new settings with existing
		mergedSettings := make(map[string]interface{})
		for k, v := range existingSettings {
			mergedSettings[k] = v
		}
		for k, v := range settings {
			mergedSettings[k] = v
		}

		// Allowed configuration keys
		allowedKeys := map[string]bool{
			"ha_enabled": true, "ha_base_url": true, "ha_token": true, "ha_websocket": true,
			"mqtt_enabled": true, "mqtt_broker": true, "mqtt_port": true, "mqtt_username": true, "mqtt_password": true,
		}

		// Validate settings structure
		for key := range settings {
			if !allowedKeys[key] {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid setting key: " + key,
				})
				return
			}

			// All values must be strings
			if _, ok := settings[key].(string); !ok {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Setting " + key + " must be a string",
				})
				return
			}
		}

		// Check if both HA and MQTT are enabled (mutual exclusion)
		haEnabled := false
		if val, ok := mergedSettings["ha_enabled"].(string); ok {
			haEnabled = val == "true"
		}
		mqttEnabled := false
		if val, ok := mergedSettings["mqtt_enabled"].(string); ok {
			mqttEnabled = val == "true"
		}

		if haEnabled && mqttEnabled {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Cannot enable both Home Assistant and MQTT integrations simultaneously. Please disable one before enabling the other.",
			})
			return
		}

		// Validate HA settings if enabled
		if haEnabled {
			haBaseURL, hasBaseURL := mergedSettings["ha_base_url"].(string)
			haToken, hasToken := mergedSettings["ha_token"].(string)

			if !hasBaseURL || haBaseURL == "" {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "HA base URL is required when HA is enabled",
				})
				return
			}
			if !hasToken || haToken == "" {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "HA access token is required when HA is enabled",
				})
				return
			}
		} else {
			// Don't include HA settings in the response when disabled (settings remain in Redis for easy re-enabling)
			delete(mergedSettings, "ha_base_url")
			delete(mergedSettings, "ha_token")
			delete(mergedSettings, "ha_websocket")
		}

		// Validate MQTT settings if enabled
		if mqttEnabled {
			mqttBroker, hasBroker := mergedSettings["mqtt_broker"].(string)

			if !hasBroker || mqttBroker == "" {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "MQTT broker is required when MQTT is enabled",
				})
				return
			}

			// Ensure MQTT port is set; default to 1883 if omitted
			mqttPort, hasPort := mergedSettings["mqtt_port"].(string)
			if !hasPort || mqttPort == "" {
				mqttPort = "1883"
				mergedSettings["mqtt_port"] = mqttPort
			}
			port, err := strconv.Atoi(mqttPort)
			if err != nil || port < 1 || port > 65535 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "MQTT port must be between 1 and 65535",
				})
				return
			}
		} else {
			// Don't include MQTT settings in the response when disabled (settings remain in Redis for easy re-enabling)
			delete(mergedSettings, "mqtt_broker")
			delete(mergedSettings, "mqtt_port")
			delete(mergedSettings, "mqtt_username")
			delete(mergedSettings, "mqtt_password")
		}

		// Save settings to Redis
		if err := client.HSet(ctx, "multizone:integrations", mergedSettings); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"error": "Failed to update integration settings",
			})
			return
		}

		// Check if HA-related settings changed
		haSettingsChanged := false
		for key := range settings {
			if key == "ha_enabled" || key == "ha_base_url" || key == "ha_token" || key == "ha_websocket" {
				haSettingsChanged = true
				break
			}
		}

		if haSettingsChanged {
			logger.Info("HA integration settings changed. Please restart the logic container for changes to take effect.")
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "updated",
			"message": "Integration settings updated successfully",
		})
	}
}

// GetDefaultsHandler returns default configuration values
func GetDefaultsHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		defaults := map[string]interface{}{
			"zone": map[string]interface{}{
				"opening_offset":          models.DefaultOpeningOffset,
				"closing_offset":          models.DefaultClosingOffset,
				"target_change_threshold": models.DefaultTargetChangeThreshold,
				"priority":                models.DefaultPriority,
			},
			"global": map[string]interface{}{
				"main_target_all_zones_satisfied": models.DefaultMainTargetAllZonesSatisfied,
				"use_average_mode":                models.DefaultUseAverageMode,
				"slider_position":                 models.DefaultSliderPosition,
				"min_valves_open":                 models.DefaultMinValvesOpen,
				"main_min_temp":                   models.DefaultMainMinTemp,
				"main_max_temp":                   models.DefaultMainMaxTemp,
				"main_change_threshold":           models.DefaultMainChangeThreshold,
				"valve_actuation_delay":           models.DefaultValveActuationDelay,
				"coordinator_interval":            models.DefaultCoordinatorInterval,
				"satisfaction_eps":                models.DefaultSatisfactionEpsilon,
			},
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(defaults)
	}
}
