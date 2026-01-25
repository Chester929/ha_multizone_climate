package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	redisv8 "github.com/go-redis/redis/v8"
	"github.com/gorilla/mux"
)

// newTestRedisClient creates a test redis client connected to miniredis
func newTestRedisClient(t *testing.T) (*redis.Client, *miniredis.Miniredis, func()) {
	t.Helper()

	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("Failed to start miniredis: %v", err)
	}

	rdb := redisv8.NewClient(&redisv8.Options{
		Addr: mr.Addr(),
	})

	// Create the internal redis.Client wrapper using the test helper
	client := redis.NewTestClient(rdb)

	cleanup := func() {
		rdb.Close()
		mr.Close()
	}

	return client, mr, cleanup
}

// TestGetDefaultsHandler tests the GetDefaultsHandler endpoint
func TestGetDefaultsHandler(t *testing.T) {
	handler := GetDefaultsHandler()

	req := httptest.NewRequest("GET", "/api/defaults", nil)
	w := httptest.NewRecorder()

	handler(w, req)

	// Check status code
	if w.Code != http.StatusOK {
		t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
	}

	// Check content type
	contentType := w.Header().Get("Content-Type")
	if contentType != "application/json" {
		t.Errorf("Expected Content-Type application/json, got %s", contentType)
	}

	// Parse response
	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	// Verify zone defaults exist
	zone, ok := response["zone"].(map[string]interface{})
	if !ok {
		t.Fatal("Expected zone defaults in response")
	}

	// Verify zone default values match constants
	if zone["opening_offset"] != models.DefaultOpeningOffset {
		t.Errorf("Expected opening_offset %.1f, got %v", models.DefaultOpeningOffset, zone["opening_offset"])
	}

	if zone["closing_offset"] != models.DefaultClosingOffset {
		t.Errorf("Expected closing_offset %.1f, got %v", models.DefaultClosingOffset, zone["closing_offset"])
	}

	if zone["target_change_threshold"] != models.DefaultTargetChangeThreshold {
		t.Errorf("Expected target_change_threshold %.1f, got %v", models.DefaultTargetChangeThreshold, zone["target_change_threshold"])
	}

	if float64(zone["priority"].(float64)) != float64(models.DefaultPriority) {
		t.Errorf("Expected priority %d, got %v", models.DefaultPriority, zone["priority"])
	}

	// Verify global defaults exist
	global, ok := response["global"].(map[string]interface{})
	if !ok {
		t.Fatal("Expected global defaults in response")
	}

	// Verify key global default values
	if float64(global["min_valves_open"].(float64)) != float64(models.DefaultMinValvesOpen) {
		t.Errorf("Expected min_valves_open %d, got %v", models.DefaultMinValvesOpen, global["min_valves_open"])
	}

	if float64(global["valve_actuation_delay"].(float64)) != float64(models.DefaultValveActuationDelay) {
		t.Errorf("Expected valve_actuation_delay %d, got %v", models.DefaultValveActuationDelay, global["valve_actuation_delay"])
	}

	if global["slider_position"] != models.DefaultSliderPosition {
		t.Errorf("Expected slider_position %.1f, got %v", models.DefaultSliderPosition, global["slider_position"])
	}
}

// TestGetDefaultsHandlerMethod tests that only GET method is supported
func TestGetDefaultsHandlerMethod(t *testing.T) {
	handler := GetDefaultsHandler()

	// Test POST method (should still work but is not the intended method)
	req := httptest.NewRequest("POST", "/api/defaults", bytes.NewBuffer([]byte("{}")))
	w := httptest.NewRecorder()

	handler(w, req)

	// The handler doesn't check method, but responds to all requests
	if w.Code != http.StatusOK {
		t.Errorf("Expected status code %d for any method, got %d", http.StatusOK, w.Code)
	}
}

// TestGetDefaultsHandlerConsistency tests that defaults are consistent
func TestGetDefaultsHandlerConsistency(t *testing.T) {
	handler := GetDefaultsHandler()

	// Make multiple requests
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest("GET", "/api/defaults", nil)
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Request %d: Expected status code %d, got %d", i, http.StatusOK, w.Code)
		}

		var response map[string]interface{}
		if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
			t.Fatalf("Request %d: Failed to decode response: %v", i, err)
		}

		// Verify consistency across requests
		zone := response["zone"].(map[string]interface{})
		if zone["opening_offset"] != models.DefaultOpeningOffset {
			t.Errorf("Request %d: Inconsistent opening_offset value", i)
		}
	}
}

// TestIntegrationStateUpdateHandler tests the state update endpoint
func TestIntegrationStateUpdateHandler(t *testing.T) {
	t.Run("InvalidJSON", func(t *testing.T) {
		handler := IntegrationStateUpdateHandler(nil)

		req := httptest.NewRequest("POST", "/api/integration/state_update", bytes.NewBufferString("invalid json"))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, w.Code)
		}
	})

	t.Run("MissingZoneID", func(t *testing.T) {
		handler := IntegrationStateUpdateHandler(nil)

		payload := map[string]interface{}{
			"current_temperature": 20.5,
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("POST", "/api/integration/state_update", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, w.Code)
		}
	})

	t.Run("ZoneNotFound", func(t *testing.T) {
		client, _, cleanup := newTestRedisClient(t)
		defer cleanup()

		handler := IntegrationStateUpdateHandler(client)

		payload := map[string]interface{}{
			"zone_id":             "nonexistent-zone",
			"current_temperature": 20.5,
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("POST", "/api/integration/state_update", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusNotFound {
			t.Errorf("Expected status code %d, got %d", http.StatusNotFound, w.Code)
		}

		var response map[string]interface{}
		json.NewDecoder(w.Body).Decode(&response)
		if response["error"] != "Zone nonexistent-zone not found" {
			t.Errorf("Expected zone not found error, got: %v", response["error"])
		}
	})

	t.Run("SuccessfulUpdate", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create a test zone in miniredis
		zoneID := "test-zone-1"
		zoneKey := "multizone:zone:" + zoneID
		mr.HSet(zoneKey, "name", "Test Zone")
		mr.HSet(zoneKey, "target_temperature", "21.0")

		handler := IntegrationStateUpdateHandler(client)

		payload := map[string]interface{}{
			"zone_id":             zoneID,
			"current_temperature": 20.5,
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("POST", "/api/integration/state_update", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		// Verify the temperature was updated in miniredis
		currentTemp := mr.HGet(zoneKey, "current_temperature")
		if currentTemp != "20.5" {
			t.Errorf("Expected current_temperature '20.5', got '%s'", currentTemp)
		}

		// Verify last_updated was set
		lastUpdated := mr.HGet(zoneKey, "last_updated")
		if lastUpdated == "" {
			t.Error("Expected last_updated to be set")
		}
	})

	t.Run("UpdateWithTargetTemperature", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create a test zone in miniredis
		zoneID := "test-zone-2"
		zoneKey := "multizone:zone:" + zoneID
		mr.HSet(zoneKey, "name", "Living Room")

		handler := IntegrationStateUpdateHandler(client)

		targetTemp := 22.5
		payload := map[string]interface{}{
			"zone_id":             zoneID,
			"current_temperature": 20.0,
			"target_temperature":  targetTemp,
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("POST", "/api/integration/state_update", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		// Verify both temperatures were updated
		currentTemp := mr.HGet(zoneKey, "current_temperature")
		if currentTemp != "20" {
			t.Errorf("Expected current_temperature '20', got '%s'", currentTemp)
		}

		updatedTargetTemp := mr.HGet(zoneKey, "target_temperature")
		if updatedTargetTemp != "22.5" {
			t.Errorf("Expected target_temperature '22.5', got '%s'", updatedTargetTemp)
		}
	})
}

// TestIntegrationDeleteCommandsHandler tests the delete commands endpoint
func TestIntegrationDeleteCommandsHandler(t *testing.T) {
	t.Run("InvalidJSON", func(t *testing.T) {
		handler := IntegrationDeleteCommandsHandler(nil)

		req := httptest.NewRequest("DELETE", "/api/integration/commands", bytes.NewBufferString("invalid json"))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, w.Code)
		}
	})

	t.Run("EmptyEntityIDs", func(t *testing.T) {
		handler := IntegrationDeleteCommandsHandler(nil)

		payload := map[string]interface{}{
			"entity_ids": []string{},
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("DELETE", "/api/integration/commands", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusBadRequest {
			t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, w.Code)
		}
	})

	t.Run("SuccessfulDelete", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create test commands in miniredis
		commandsKey := "multizone:commands"
		cmd1 := map[string]interface{}{
			"action": "set_temperature",
			"value":  21.5,
		}
		cmd1JSON, _ := json.Marshal(cmd1)
		mr.HSet(commandsKey, "climate.bedroom", string(cmd1JSON))

		cmd2 := map[string]interface{}{
			"action": "turn_on",
		}
		cmd2JSON, _ := json.Marshal(cmd2)
		mr.HSet(commandsKey, "switch.valve1", string(cmd2JSON))

		handler := IntegrationDeleteCommandsHandler(client)

		payload := map[string]interface{}{
			"entity_ids": []string{"climate.bedroom", "switch.valve1"},
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("DELETE", "/api/integration/commands", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		// Verify commands were deleted from miniredis
		// miniredis doesn't have HExists, so we use HGet and check for empty string
		if mr.HGet(commandsKey, "climate.bedroom") != "" {
			t.Error("Expected climate.bedroom command to be deleted")
		}
		if mr.HGet(commandsKey, "switch.valve1") != "" {
			t.Error("Expected switch.valve1 command to be deleted")
		}
	})

	t.Run("PartialDelete", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create test commands in miniredis
		commandsKey := "multizone:commands"
		cmd1 := map[string]interface{}{
			"action": "set_temperature",
			"value":  21.5,
		}
		cmd1JSON, _ := json.Marshal(cmd1)
		mr.HSet(commandsKey, "climate.bedroom", string(cmd1JSON))

		cmd2 := map[string]interface{}{
			"action": "turn_on",
		}
		cmd2JSON, _ := json.Marshal(cmd2)
		mr.HSet(commandsKey, "switch.valve1", string(cmd2JSON))

		cmd3 := map[string]interface{}{
			"action": "turn_off",
		}
		cmd3JSON, _ := json.Marshal(cmd3)
		mr.HSet(commandsKey, "switch.valve2", string(cmd3JSON))

		handler := IntegrationDeleteCommandsHandler(client)

		// Delete only some commands
		payload := map[string]interface{}{
			"entity_ids": []string{"climate.bedroom"},
		}
		body, _ := json.Marshal(payload)

		req := httptest.NewRequest("DELETE", "/api/integration/commands", bytes.NewBuffer(body))
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		// Verify only specified command was deleted
		if mr.HGet(commandsKey, "climate.bedroom") != "" {
			t.Error("Expected climate.bedroom command to be deleted")
		}
		if mr.HGet(commandsKey, "switch.valve1") == "" {
			t.Error("Expected switch.valve1 command to remain")
		}
		if mr.HGet(commandsKey, "switch.valve2") == "" {
			t.Error("Expected switch.valve2 command to remain")
		}
	})
}

// TestIntegrationGetCommandsHandler tests the get commands endpoint
func TestIntegrationGetCommandsHandler(t *testing.T) {
	t.Run("EmptyCommandQueue", func(t *testing.T) {
		client, _, cleanup := newTestRedisClient(t)
		defer cleanup()

		handler := IntegrationGetCommandsHandler(client)

		req := httptest.NewRequest("GET", "/api/integration/commands", nil)
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		var response map[string]interface{}
		if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
			t.Fatalf("Failed to decode response: %v", err)
		}

		// Should return an empty array, not nil
		commands, ok := response["commands"].([]interface{})
		if !ok {
			t.Fatalf("Expected commands to be an array, got: %T (%v)", response["commands"], response["commands"])
		}

		if len(commands) != 0 {
			t.Errorf("Expected 0 commands, got %d", len(commands))
		}
	})

	t.Run("SingleCommand", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create a test command in miniredis
		commandsKey := "multizone:commands"
		cmd := map[string]interface{}{
			"action": "set_temperature",
			"value":  21.5,
		}
		cmdJSON, _ := json.Marshal(cmd)
		mr.HSet(commandsKey, "climate.main_thermostat", string(cmdJSON))

		handler := IntegrationGetCommandsHandler(client)

		req := httptest.NewRequest("GET", "/api/integration/commands", nil)
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		var response map[string]interface{}
		json.NewDecoder(w.Body).Decode(&response)

		commands, ok := response["commands"].([]interface{})
		if !ok {
			t.Fatal("Expected commands array in response")
		}

		if len(commands) != 1 {
			t.Fatalf("Expected 1 command, got %d", len(commands))
		}

		command := commands[0].(map[string]interface{})
		if command["entity_id"] != "climate.main_thermostat" {
			t.Errorf("Expected entity_id 'climate.main_thermostat', got '%v'", command["entity_id"])
		}
		if command["action"] != "set_temperature" {
			t.Errorf("Expected action 'set_temperature', got '%v'", command["action"])
		}
		if command["value"] != 21.5 {
			t.Errorf("Expected value 21.5, got %v", command["value"])
		}
	})

	t.Run("MultipleCommands", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create multiple test commands in miniredis
		commandsKey := "multizone:commands"

		cmd1 := map[string]interface{}{
			"action": "set_temperature",
			"value":  21.5,
		}
		cmd1JSON, _ := json.Marshal(cmd1)
		mr.HSet(commandsKey, "climate.main_thermostat", string(cmd1JSON))

		cmd2 := map[string]interface{}{
			"action": "turn_on",
		}
		cmd2JSON, _ := json.Marshal(cmd2)
		mr.HSet(commandsKey, "switch.valve_bedroom", string(cmd2JSON))

		cmd3 := map[string]interface{}{
			"action": "turn_off",
		}
		cmd3JSON, _ := json.Marshal(cmd3)
		mr.HSet(commandsKey, "switch.valve_living_room", string(cmd3JSON))

		handler := IntegrationGetCommandsHandler(client)

		req := httptest.NewRequest("GET", "/api/integration/commands", nil)
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		var response map[string]interface{}
		json.NewDecoder(w.Body).Decode(&response)

		commands, ok := response["commands"].([]interface{})
		if !ok {
			t.Fatal("Expected commands array in response")
		}

		if len(commands) != 3 {
			t.Fatalf("Expected 3 commands, got %d", len(commands))
		}

		// Verify commands contain expected entity IDs
		entityIDs := make(map[string]bool)
		for _, cmd := range commands {
			command := cmd.(map[string]interface{})
			entityIDs[command["entity_id"].(string)] = true
		}

		expectedEntities := []string{
			"climate.main_thermostat",
			"switch.valve_bedroom",
			"switch.valve_living_room",
		}

		for _, entity := range expectedEntities {
			if !entityIDs[entity] {
				t.Errorf("Expected entity '%s' not found in commands", entity)
			}
		}
	})

	t.Run("CommandWithoutValue", func(t *testing.T) {
		client, mr, cleanup := newTestRedisClient(t)
		defer cleanup()

		// Create a test command without a value field
		commandsKey := "multizone:commands"
		cmd := map[string]interface{}{
			"action": "turn_on",
		}
		cmdJSON, _ := json.Marshal(cmd)
		mr.HSet(commandsKey, "switch.valve1", string(cmdJSON))

		handler := IntegrationGetCommandsHandler(client)

		req := httptest.NewRequest("GET", "/api/integration/commands", nil)
		w := httptest.NewRecorder()

		handler(w, req)

		if w.Code != http.StatusOK {
			t.Errorf("Expected status code %d, got %d", http.StatusOK, w.Code)
		}

		var response map[string]interface{}
		json.NewDecoder(w.Body).Decode(&response)

		commands, ok := response["commands"].([]interface{})
		if !ok {
			t.Fatal("Expected commands array in response")
		}

		if len(commands) != 1 {
			t.Fatalf("Expected 1 command, got %d", len(commands))
		}

		command := commands[0].(map[string]interface{})
		if command["entity_id"] != "switch.valve1" {
			t.Errorf("Expected entity_id 'switch.valve1', got '%v'", command["entity_id"])
		}
		if command["action"] != "turn_on" {
			t.Errorf("Expected action 'turn_on', got '%v'", command["action"])
		}
		// Value should be nil or not present for commands without a value
		if _, exists := command["value"]; exists && command["value"] != nil {
			t.Errorf("Expected no value field, got %v", command["value"])
		}
	})
}

// TestCreateZoneWithAdvancedParameters tests creating a zone with all advanced parameters
func TestCreateZoneWithAdvancedParameters(t *testing.T) {
	client, mr, cleanup := newTestRedisClient(t)
	defer cleanup()

	handler := CreateZoneHandler(client, nil)

	zoneID := "test-zone-advanced"
	payload := map[string]interface{}{
		"id":                       zoneID,
		"name":                     "Advanced Test Zone",
		"opening_offset":           "0.5",
		"closing_offset":           "0.4",
		"target_change_threshold":  "0.2",
		"is_fallback_valve":        "true",
		"target_temperature":       "21.5",
		"temperature_sensor_entity_id": "sensor.test_temp",
		"valve_switch_entity_id":   "switch.test_valve",
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest("POST", "/api/zones", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	handler(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("Expected status code %d, got %d. Body: %s", http.StatusCreated, w.Code, w.Body.String())
	}

	// Verify all advanced parameters were saved to Redis correctly
	zoneKey := "multizone:zone:" + zoneID

	openingOffset := mr.HGet(zoneKey, "opening_offset")
	if openingOffset != "0.5" {
		t.Errorf("Expected opening_offset '0.5', got '%s'", openingOffset)
	}

	closingOffset := mr.HGet(zoneKey, "closing_offset")
	if closingOffset != "0.4" {
		t.Errorf("Expected closing_offset '0.4', got '%s'", closingOffset)
	}

	targetChangeThreshold := mr.HGet(zoneKey, "target_change_threshold")
	if targetChangeThreshold != "0.2" {
		t.Errorf("Expected target_change_threshold '0.2', got '%s'", targetChangeThreshold)
	}

	isFallbackValve := mr.HGet(zoneKey, "is_fallback_valve")
	if isFallbackValve != "true" {
		t.Errorf("Expected is_fallback_valve 'true', got '%s'", isFallbackValve)
	}

	// Verify other fields were also saved correctly
	name := mr.HGet(zoneKey, "name")
	if name != "Advanced Test Zone" {
		t.Errorf("Expected name 'Advanced Test Zone', got '%s'", name)
	}

	targetTemp := mr.HGet(zoneKey, "target_temperature")
	if targetTemp != "21.5" {
		t.Errorf("Expected target_temperature '21.5', got '%s'", targetTemp)
	}
}

// TestCreateZoneWithDefaultAdvancedParameters tests creating a zone without advanced parameters
func TestCreateZoneWithDefaultAdvancedParameters(t *testing.T) {
	client, mr, cleanup := newTestRedisClient(t)
	defer cleanup()

	handler := CreateZoneHandler(client, nil)

	zoneID := "test-zone-defaults"
	payload := map[string]interface{}{
		"id":   zoneID,
		"name": "Default Parameters Zone",
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest("POST", "/api/zones", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	handler(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("Expected status code %d, got %d. Body: %s", http.StatusCreated, w.Code, w.Body.String())
	}

	// Verify defaults are applied (0.3, 0.3, 0.1, false)
	zoneKey := "multizone:zone:" + zoneID

	openingOffset := mr.HGet(zoneKey, "opening_offset")
	if openingOffset != "0.3" {
		t.Errorf("Expected default opening_offset '0.3', got '%s'", openingOffset)
	}

	closingOffset := mr.HGet(zoneKey, "closing_offset")
	if closingOffset != "0.3" {
		t.Errorf("Expected default closing_offset '0.3', got '%s'", closingOffset)
	}

	targetChangeThreshold := mr.HGet(zoneKey, "target_change_threshold")
	if targetChangeThreshold != "0.1" {
		t.Errorf("Expected default target_change_threshold '0.1', got '%s'", targetChangeThreshold)
	}

	isFallbackValve := mr.HGet(zoneKey, "is_fallback_valve")
	if isFallbackValve != "false" {
		t.Errorf("Expected default is_fallback_valve 'false', got '%s'", isFallbackValve)
	}
}

// TestUpdateZoneAdvancedParameters tests updating existing zone's advanced parameters
func TestUpdateZoneAdvancedParameters(t *testing.T) {
	client, mr, cleanup := newTestRedisClient(t)
	defer cleanup()

	// Create a test zone first
	zoneID := "test-zone-update"
	zoneKey := "multizone:zone:" + zoneID
	mr.HSet(zoneKey, "name", "Test Zone")
	mr.HSet(zoneKey, "opening_offset", "0.3")
	mr.HSet(zoneKey, "closing_offset", "0.3")
	mr.HSet(zoneKey, "target_change_threshold", "0.1")
	mr.HSet(zoneKey, "is_fallback_valve", "false")

	handler := UpdateZoneHandler(client, nil)

	// Update the advanced parameters
	updates := map[string]interface{}{
		"opening_offset":          "0.6",
		"closing_offset":          "0.7",
		"target_change_threshold": "0.15",
		"is_fallback_valve":       "true",
	}
	body, _ := json.Marshal(updates)

	req := httptest.NewRequest("PUT", "/api/zones/"+zoneID, bytes.NewBuffer(body))
	// Simulate mux.Vars by creating a context with the zone ID
	req = mux.SetURLVars(req, map[string]string{"id": zoneID})
	w := httptest.NewRecorder()

	handler(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected status code %d, got %d. Body: %s", http.StatusOK, w.Code, w.Body.String())
	}

	// Verify changes in Redis
	openingOffset := mr.HGet(zoneKey, "opening_offset")
	if openingOffset != "0.6" {
		t.Errorf("Expected updated opening_offset '0.6', got '%s'", openingOffset)
	}

	closingOffset := mr.HGet(zoneKey, "closing_offset")
	if closingOffset != "0.7" {
		t.Errorf("Expected updated closing_offset '0.7', got '%s'", closingOffset)
	}

	targetChangeThreshold := mr.HGet(zoneKey, "target_change_threshold")
	if targetChangeThreshold != "0.15" {
		t.Errorf("Expected updated target_change_threshold '0.15', got '%s'", targetChangeThreshold)
	}

	isFallbackValve := mr.HGet(zoneKey, "is_fallback_valve")
	if isFallbackValve != "true" {
		t.Errorf("Expected updated is_fallback_valve 'true', got '%s'", isFallbackValve)
	}

	// Verify original name wasn't changed
	name := mr.HGet(zoneKey, "name")
	if name != "Test Zone" {
		t.Errorf("Expected name to remain 'Test Zone', got '%s'", name)
	}
}

// TestCreateZoneInvalidAdvancedParameters tests validation failures for advanced parameters
func TestCreateZoneInvalidAdvancedParameters(t *testing.T) {
	testCases := []struct {
		name          string
		payload       map[string]interface{}
		expectedError string
	}{
		{
			name: "NegativeOpeningOffset",
			payload: map[string]interface{}{
				"name":           "Test Zone",
				"opening_offset": "-0.5",
			},
			expectedError: "Opening offset must be between 0.0 and 5.0",
		},
		{
			name: "TooLargeOpeningOffset",
			payload: map[string]interface{}{
				"name":           "Test Zone",
				"opening_offset": "6.0",
			},
			expectedError: "Opening offset must be between 0.0 and 5.0",
		},
		{
			name: "InvalidOpeningOffsetNotANumber",
			payload: map[string]interface{}{
				"name":           "Test Zone",
				"opening_offset": "not-a-number",
			},
			expectedError: "Opening offset must be between 0.0 and 5.0",
		},
		{
			name: "NegativeClosingOffset",
			payload: map[string]interface{}{
				"name":           "Test Zone",
				"closing_offset": "-0.3",
			},
			expectedError: "Closing offset must be between 0.0 and 5.0",
		},
		{
			name: "TooLargeClosingOffset",
			payload: map[string]interface{}{
				"name":           "Test Zone",
				"closing_offset": "10.0",
			},
			expectedError: "Closing offset must be between 0.0 and 5.0",
		},
		{
			name: "NegativeTargetChangeThreshold",
			payload: map[string]interface{}{
				"name":                    "Test Zone",
				"target_change_threshold": "-0.1",
			},
			expectedError: "Target change threshold must be between 0.0 and 5.0",
		},
		{
			name: "TooLargeTargetChangeThreshold",
			payload: map[string]interface{}{
				"name":                    "Test Zone",
				"target_change_threshold": "5.5",
			},
			expectedError: "Target change threshold must be between 0.0 and 5.0",
		},
		{
			name: "InvalidIsFallbackValveNotBoolean",
			payload: map[string]interface{}{
				"name":              "Test Zone",
				"is_fallback_valve": "yes",
			},
			expectedError: "Is fallback valve must be either 'true' or 'false'",
		},
		{
			name: "InvalidIsFallbackValveNumber",
			payload: map[string]interface{}{
				"name":              "Test Zone",
				"is_fallback_valve": "1",
			},
			expectedError: "Is fallback valve must be either 'true' or 'false'",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			client, _, cleanup := newTestRedisClient(t)
			defer cleanup()

			handler := CreateZoneHandler(client, nil)

			body, _ := json.Marshal(tc.payload)
			req := httptest.NewRequest("POST", "/api/zones", bytes.NewBuffer(body))
			w := httptest.NewRecorder()

			handler(w, req)

			if w.Code != http.StatusBadRequest {
				t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, w.Code)
			}

			var response map[string]interface{}
			if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
				t.Fatalf("Failed to decode response: %v", err)
			}

			errorMsg, ok := response["error"].(string)
			if !ok {
				t.Fatalf("Expected error message in response, got: %v", response)
			}

			if errorMsg != tc.expectedError {
				t.Errorf("Expected error '%s', got '%s'", tc.expectedError, errorMsg)
			}
		})
	}
}
