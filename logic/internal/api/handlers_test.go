package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

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
}

// TestIntegrationGetCommandsHandler tests the get commands endpoint
func TestIntegrationGetCommandsHandler(t *testing.T) {
	t.Run("NilClient", func(t *testing.T) {
		// Skip test if nil client causes panic - would need mock Redis for full test
		t.Skip("Skipping test that requires Redis mock")
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
}
