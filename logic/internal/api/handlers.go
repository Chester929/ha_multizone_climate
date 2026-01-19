package api

import (
	"context"
	"encoding/json"
	"net/http"
	"regexp"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/algorithm"
	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/gorilla/mux"
)

const (
	// entityIDPattern validates Home Assistant entity IDs (domain.entity_name)
	entityIDPatternString = `^[a-z_]+\.[a-z0-9_]+$`
)

// entityIDPattern is compiled once at package initialization
var entityIDPattern = regexp.MustCompile(entityIDPatternString)

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

		zones := []models.ZoneState{}
		for _, key := range zoneKeys {
			zoneData, err := client.HGetAll(ctx, key)
			if err != nil {
				continue
			}

			// Simple zone construction (in full impl, would parse all fields)
			zone := models.ZoneState{
				ID:   zoneData["id"],
				Name: zoneData["name"],
			}
			zones = append(zones, zone)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(zones)
	}
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

// UpdateZoneHandler updates a zone
func UpdateZoneHandler(client *redis.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		vars := mux.Vars(r)
		zoneID := vars["id"]

		var updates map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		ctx := context.Background()
		key := "multizone:zone:" + zoneID

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
