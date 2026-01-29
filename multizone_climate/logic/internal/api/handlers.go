package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strconv"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/algorithm"
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/chester929/ha_multizone_climate/logic/internal/statistics"
	redisv8 "github.com/go-redis/redis/v8"
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
func CreateZoneHandler(client *redis.Client, integration interface{}) http.HandlerFunc {
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
		if climateEntity, ok := zone["climate_entity_id"].(string); ok && climateEntity != "" {
			if !entityIDPattern.MatchString(climateEntity) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Invalid climate entity ID format, expected format: domain.entity_name",
				})
				return
			}
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

		// Validate opening_offset if provided
		if rawOpeningOffset, exists := zone["opening_offset"]; exists {
			var openingOffset string
			switch v := rawOpeningOffset.(type) {
			case string:
				openingOffset = v
			case float64:
				openingOffset = strconv.FormatFloat(v, 'f', -1, 64)
			case int:
				openingOffset = strconv.Itoa(v)
			case int64:
				openingOffset = strconv.FormatInt(v, 10)
			case json.Number:
				openingOffset = v.String()
			}
			if openingOffset != "" {
				if err := validateTemperatureOffset(openingOffset, "Opening offset"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
			}
		}

		// Validate closing_offset if provided
		if rawClosingOffset, exists := zone["closing_offset"]; exists {
			var closingOffset string
			switch v := rawClosingOffset.(type) {
			case string:
				closingOffset = v
			case float64:
				closingOffset = strconv.FormatFloat(v, 'f', -1, 64)
			case int:
				closingOffset = strconv.Itoa(v)
			case int64:
				closingOffset = strconv.FormatInt(v, 10)
			case json.Number:
				closingOffset = v.String()
			}
			if closingOffset != "" {
				if err := validateTemperatureOffset(closingOffset, "Closing offset"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
			}
		}

		// Validate target_change_threshold if provided
		if rawTargetChangeThreshold, exists := zone["target_change_threshold"]; exists {
			var targetChangeThreshold string
			switch v := rawTargetChangeThreshold.(type) {
			case string:
				targetChangeThreshold = v
			case float64:
				targetChangeThreshold = strconv.FormatFloat(v, 'f', -1, 64)
			case int:
				targetChangeThreshold = strconv.Itoa(v)
			case int64:
				targetChangeThreshold = strconv.FormatInt(v, 10)
			case json.Number:
				targetChangeThreshold = v.String()
			}
			if targetChangeThreshold != "" {
				if err := validateTemperatureOffset(targetChangeThreshold, "Target change threshold"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
			}
		}

		// Validate is_fallback_valve if provided; accept both string and boolean values
		if rawFallbackValve, exists := zone["is_fallback_valve"]; exists {
			var isFallbackValve string

			switch v := rawFallbackValve.(type) {
			case string:
				isFallbackValve = v
			case bool:
				// Normalize boolean to string so that validation and later processing work consistently
				isFallbackValve = strconv.FormatBool(v)
				zone["is_fallback_valve"] = isFallbackValve
			default:
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Is fallback valve must be a boolean or a boolean-like string",
				})
				return
			}

			if isFallbackValve != "" {
				if err := validateBoolean(isFallbackValve, "Is fallback valve"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
			}
		}

		// Set defaults for missing fields
		zoneData := map[string]interface{}{
			"id":                           zoneID,
			"name":                         name,
			"enabled":                      getStringOrDefault(zone, "enabled", "true"),
			"target_temperature":           getStringOrDefault(zone, "target_temperature", "20"),
			"satisfaction":                 getStringOrDefault(zone, "satisfaction", "unknown"),
			"valve_state":                  getStringOrDefault(zone, "valve_state", "closed"),
			"priority":                     getStringOrDefault(zone, "priority", "0"),
			"temperature_sensor_entity_id": getStringOrDefault(zone, "temperature_sensor_entity_id", ""),
			"valve_switch_entity_id":       getStringOrDefault(zone, "valve_switch_entity_id", ""),
			"climate_entity_id":            getStringOrDefault(zone, "climate_entity_id", ""),
			"opening_offset":               getStringOrDefault(zone, "opening_offset", "0.3"),
			"closing_offset":               getStringOrDefault(zone, "closing_offset", "0.3"),
			"target_change_threshold":      getStringOrDefault(zone, "target_change_threshold", "0.1"),
			"is_fallback_valve":            getStringOrDefault(zone, "is_fallback_valve", "false"),
		}

		// Only set current_temperature if it's provided and not empty
		if currentTemp, ok := zone["current_temperature"].(string); ok && currentTemp != "" {
			zoneData["current_temperature"] = currentTemp
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
func UpdateZoneHandler(client *redis.Client, integration interface{}) http.HandlerFunc {
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

		// Validate opening_offset if provided
		if rawOpeningOffset, exists := updates["opening_offset"]; exists {
			var openingOffsetStr string

			switch v := rawOpeningOffset.(type) {
			case string:
				openingOffsetStr = v
			case float64:
				openingOffsetStr = strconv.FormatFloat(v, 'f', -1, 64)
			default:
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": fmt.Sprintf("Opening offset has invalid type %T", rawOpeningOffset),
				})
				return
			}

			if openingOffsetStr != "" {
				if err := validateTemperatureOffset(openingOffsetStr, "Opening offset"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
				// Store normalized, validated value back into updates
				updates["opening_offset"] = openingOffsetStr
			}
		}

		// Validate closing_offset if provided
		if closingOffset, ok := updates["closing_offset"].(string); ok && closingOffset != "" {
			if err := validateTemperatureOffset(closingOffset, "Closing offset"); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": err.Error(),
				})
				return
			}
		}

		// Validate target_change_threshold if provided
		if rawValue, exists := updates["target_change_threshold"]; exists {
			var targetChangeThreshold string

			switch v := rawValue.(type) {
			case string:
				targetChangeThreshold = v
			case float64:
				// JSON numbers are decoded as float64; normalize to string for validation/storage
				targetChangeThreshold = strconv.FormatFloat(v, 'f', -1, 64)
			default:
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error": "Target change threshold must be a string or number",
				})
				return
			}

			if targetChangeThreshold != "" {
				if err := validateTemperatureOffset(targetChangeThreshold, "Target change threshold"); err != nil {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusBadRequest)
					json.NewEncoder(w).Encode(map[string]interface{}{
						"error": err.Error(),
					})
					return
				}
			}

			// Ensure the normalized string value is stored back into the updates map
			updates["target_change_threshold"] = targetChangeThreshold
		}

		// Validate is_fallback_valve if provided
		if isFallbackValve, ok := updates["is_fallback_valve"].(string); ok && isFallbackValve != "" {
			if err := validateBoolean(isFallbackValve, "Is fallback valve"); err != nil {
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

// Helper function to validate temperature offset range (opening/closing offsets)
func validateTemperatureOffset(offsetStr string, fieldName string) error {
	offset, err := strconv.ParseFloat(offsetStr, 64)
	if err != nil || offset < 0.0 || offset > 5.0 {
		return fmt.Errorf("%s must be between 0.0 and 5.0", fieldName)
	}
	return nil
}

// Helper function to validate boolean string
func validateBoolean(boolStr string, fieldName string) error {
	if boolStr != "true" && boolStr != "false" {
		return fmt.Errorf("%s must be either 'true' or 'false'", fieldName)
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

// GetIntegrationSettingsHandler returns empty integration settings (no integrations available)
func GetIntegrationSettingsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Return empty settings since all integrations have been removed
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{})
	}
}

// UpdateIntegrationSettingsHandler accepts but ignores integration settings (no integrations available)
func UpdateIntegrationSettingsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Accept the request but don't do anything since integrations are removed
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "ignored",
			"message": "Integration settings are not used in addon-only mode",
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

// IntegrationStateUpdateHandler handles state updates from the Home Assistant integration
// POST /api/integration/state_update
func IntegrationStateUpdateHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var update struct {
			ZoneID             string   `json:"zone_id"`
			CurrentTemperature float64  `json:"current_temperature"`
			TargetTemperature  *float64 `json:"target_temperature,omitempty"`
		}

		if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
			logger.Error("Failed to decode state update: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Invalid JSON payload",
			})
			return
		}

		// Validate required fields
		if update.ZoneID == "" {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "zone_id is required",
			})
			return
		}

		ctx := r.Context()

		// Check if zone exists
		zoneKey := fmt.Sprintf("multizone:zone:%s", update.ZoneID)
		exists, err := client.Exists(ctx, zoneKey)
		if err != nil {
			logger.Error("Failed to check zone existence: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Database error",
			})
			return
		}

		if exists == 0 {
			w.WriteHeader(http.StatusNotFound)
			json.NewEncoder(w).Encode(map[string]string{
				"error": fmt.Sprintf("Zone %s not found", update.ZoneID),
			})
			return
		}

		// Update zone state in Redis
		updates := []interface{}{
			"current_temperature", update.CurrentTemperature,
			"last_updated", time.Now().Format(time.RFC3339),
		}

		if update.TargetTemperature != nil && *update.TargetTemperature > 0 {
			updates = append(updates, "target_temperature", *update.TargetTemperature)
		}

		if err := client.HSet(ctx, zoneKey, updates...); err != nil {
			logger.Error("Failed to update zone state: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Failed to update zone state",
			})
			return
		}

		logger.Info("Integration state update: zone=%s, current_temp=%.1f°C", update.ZoneID, update.CurrentTemperature)

		// Trigger temperature calculation job
		jobData := map[string]interface{}{
			"zone_id": update.ZoneID,
		}
		jobJSON, err := json.Marshal(jobData)
		if err != nil {
			logger.Error("Failed to marshal calculation job data: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Failed to enqueue calculation job",
			})
			return
		}
		if err := client.LPush(ctx, "multizone:jobs:calculate_temp", string(jobJSON)); err != nil {
			logger.Error("Failed to enqueue calculation job: %v", err)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "success",
		})
	}
}

// IntegrationGetCommandsHandler retrieves pending commands for the integration to execute
// GET /api/integration/commands
func IntegrationGetCommandsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		ctx := r.Context()

		commandsKey := "multizone:commands"

		// Get all commands from the hash
		commands, err := client.HGetAll(ctx, commandsKey)
		if err != nil && !errors.Is(err, redisv8.Nil) {
			logger.Error("Failed to retrieve commands: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Failed to retrieve commands",
			})
			return
		}

		// Convert to structured response
		type Command struct {
			EntityID string      `json:"entity_id"`
			Action   string      `json:"action"`
			Value    interface{} `json:"value,omitempty"`
		}

		// Initialize as empty slice to ensure JSON returns [] instead of null
		commandList := make([]Command, 0)

		for entityID, commandData := range commands {
			var cmd map[string]interface{}
			if err := json.Unmarshal([]byte(commandData), &cmd); err != nil {
				logger.Error("Failed to parse command for %s: %v", entityID, err)
				continue
			}

			command := Command{
				EntityID: entityID,
				Action:   fmt.Sprintf("%v", cmd["action"]),
			}

			if value, ok := cmd["value"]; ok {
				command.Value = value
			}

			commandList = append(commandList, command)
		}

		if len(commandList) > 0 {
			logger.Info("Integration polling: returning %d commands", len(commandList))
		}

		json.NewEncoder(w).Encode(map[string]interface{}{
			"commands": commandList,
		})
	}
}

// IntegrationDeleteCommandsHandler acknowledges execution of commands
// DELETE /api/integration/commands
func IntegrationDeleteCommandsHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var request struct {
			EntityIDs []string `json:"entity_ids"`
		}

		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			logger.Error("Failed to decode delete request: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Invalid JSON payload",
			})
			return
		}

		if len(request.EntityIDs) == 0 {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "entity_ids is required",
			})
			return
		}

		ctx := r.Context()
		commandsKey := "multizone:commands"

		// Delete specific commands from the hash
		if err := client.HDel(ctx, commandsKey, request.EntityIDs...); err != nil {
			logger.Error("Failed to delete commands: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Failed to delete commands",
			})
			return
		}

		logger.Info("Integration acknowledged %d commands", len(request.EntityIDs))

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "success",
		})
	}
}

// IntegrationGetStateHandler returns the current system state for the integration
// GET /api/integration/state
func IntegrationGetStateHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		ctx := r.Context()

		// Get global configuration
		configRaw, err := client.HGetAll(ctx, "multizone:config")
		if err != nil {
			logger.Error("Failed to retrieve configuration: %v", err)
			configRaw = make(map[string]string)
		}

		// Convert config to proper types
		config := make(map[string]interface{})
		for k, v := range configRaw {
			// Convert integer config values
			if k == "min_valves_open" || k == "valve_actuation_delay" || k == "coordinator_interval" {
				if intVal, err := strconv.Atoi(v); err == nil {
					config[k] = intVal
				} else {
					config[k] = v
				}
				// Convert float config values
			} else if k == "main_target_all_zones_satisfied" || k == "main_min_temp" || k == "main_max_temp" || k == "main_change_threshold" || k == "satisfaction_eps" {
				if floatVal, err := strconv.ParseFloat(v, 64); err == nil {
					config[k] = floatVal
				} else {
					config[k] = v
				}
				// Convert boolean config values
			} else if k == "use_average_mode" || k == "multizone_enabled" {
				config[k] = v == "true" || v == "True" || v == "1"
			} else {
				config[k] = v
			}
		}

		// Get all zones
		zoneKeys, err := client.Keys(ctx, "multizone:zone:*")
		if err != nil {
			logger.Error("Failed to retrieve zone keys: %v", err)
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{
				"error": "Failed to retrieve zone keys",
			})
			return
		}

		zones := make(map[string]map[string]interface{})
		for _, key := range zoneKeys {
			zoneData, err := client.HGetAll(ctx, key)
			if err != nil {
				continue
			}

			// Extract zone ID from key (multizone:zone:ZONE_ID)
			zoneID := key[len("multizone:zone:"):]

			// Convert zone data to interface map and parse numeric values
			zoneMap := make(map[string]interface{})
			for k, v := range zoneData {
				// Try to parse numeric values
				if k == "current_temperature" || k == "target_temperature" {
					if floatVal, err := strconv.ParseFloat(v, 64); err == nil {
						zoneMap[k] = floatVal
					} else {
						zoneMap[k] = v
					}
				} else if k == "priority" {
					if intVal, err := strconv.Atoi(v); err == nil {
						zoneMap[k] = intVal
					} else {
						zoneMap[k] = v
					}
				} else if k == "temperature_rising" || k == "temperature_falling" {
					zoneMap[k] = v == "true" || v == "True" || v == "1"
				} else {
					zoneMap[k] = v
				}
			}

			zones[zoneID] = zoneMap
		}

		// Get main climate state from multizone:main_climate
		mainClimateData, err := client.HGetAll(ctx, "multizone:main_climate")
		if err != nil {
			logger.Error("Failed to retrieve main climate state: %v", err)
			mainClimateData = make(map[string]string)
		}

		mainClimate := make(map[string]interface{})

		// Parse main climate entity state
		if entityID, ok := mainClimateData["entity_id"]; ok && entityID != "" {
			mainClimate["entity_id"] = entityID
		}

		// Parse numeric values from main climate state
		if currentTemp, ok := mainClimateData["current_temperature"]; ok && currentTemp != "" {
			if floatVal, err := strconv.ParseFloat(currentTemp, 64); err == nil {
				mainClimate["current_temperature"] = floatVal
			}
		}

		if targetTemp, ok := mainClimateData["target_temperature"]; ok && targetTemp != "" {
			if floatVal, err := strconv.ParseFloat(targetTemp, 64); err == nil {
				mainClimate["target_temperature"] = floatVal
			}
		}

		if outdoorTemp, ok := mainClimateData["outdoor_temperature"]; ok && outdoorTemp != "" {
			if floatVal, err := strconv.ParseFloat(outdoorTemp, 64); err == nil {
				mainClimate["outdoor_temperature"] = floatVal
			}
		}

		if hvacMode, ok := mainClimateData["hvac_mode"]; ok {
			mainClimate["hvac_mode"] = hvacMode
		}

		if hvacAction, ok := mainClimateData["hvac_action"]; ok {
			mainClimate["hvac_action"] = hvacAction
		}

		// Get multizone_enabled from config (it's a configuration setting, not runtime state)
		if multizoneEnabled, ok := config["multizone_enabled"]; ok {
			// config["multizone_enabled"] is already converted to bool above
			mainClimate["multizone_enabled"] = multizoneEnabled
		}

		// Get job queue sizes
		calculateQueueSize, _ := client.LLen(ctx, "multizone:jobs:calculate_main_temp")
		valveQueueSize, _ := client.LLen(ctx, "multizone:jobs:update_valves")

		// Calculate open valve count from zones
		openValveCount := 0
		for _, zoneData := range zones {
			if valveState, ok := zoneData["valve_state"].(string); ok && valveState == "open" {
				openValveCount++
			}
		}

		// Build response
		response := map[string]interface{}{
			"config":               config,
			"main_climate":         mainClimate,
			"zones":                zones,
			"calculate_queue_size": calculateQueueSize,
			"valve_queue_size":     valveQueueSize,
			"open_valve_count":     openValveCount,
		}

		json.NewEncoder(w).Encode(response)
	}
}
