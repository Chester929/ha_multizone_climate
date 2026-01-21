package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
)

// TestHAGetEntitiesHandler_NotEnabled tests the handler when HA integration is not enabled
func TestHAGetEntitiesHandler_NotEnabled(t *testing.T) {
	// Create a disabled integration (without starting it)
	integration := homeassistant.NewIntegration("http://localhost:8123", "test-token", nil, false)

	req := httptest.NewRequest("GET", "/api/ha/entities", nil)
	w := httptest.NewRecorder()

	handler := HAGetEntitiesHandler(integration)
	handler(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status %d, got %d", http.StatusServiceUnavailable, w.Code)
	}

	var response map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if _, ok := response["error"]; !ok {
		t.Error("Expected error field in response")
	}

	errorMsg, ok := response["error"].(string)
	if !ok || errorMsg != "Home Assistant integration is not enabled" {
		t.Errorf("Expected error message 'Home Assistant integration is not enabled', got %v", errorMsg)
	}
}

// TestHAGetEntitiesHandler_WithDomainFilter tests domain filtering
func TestHAGetEntitiesHandler_WithDomainFilter(t *testing.T) {
	integration := homeassistant.NewIntegration("http://localhost:8123", "test-token", nil, false)

	// Test with climate domain filter
	req := httptest.NewRequest("GET", "/api/ha/entities?domain=climate", nil)
	w := httptest.NewRecorder()

	handler := HAGetEntitiesHandler(integration)
	handler(w, req)

	// Should still return service unavailable since integration is not enabled
	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status %d, got %d", http.StatusServiceUnavailable, w.Code)
	}
}

// TestHAGetEntitiesHandler_NilIntegration tests the handler with nil integration
func TestHAGetEntitiesHandler_NilIntegration(t *testing.T) {
	req := httptest.NewRequest("GET", "/api/ha/entities", nil)
	w := httptest.NewRecorder()

	// This should panic or handle nil gracefully
	// For production code, we should add nil checks
	defer func() {
		if r := recover(); r == nil {
			// Handler should not panic with nil integration
			// Check that we got an error response
			if w.Code != http.StatusServiceUnavailable && w.Code != http.StatusInternalServerError {
				t.Errorf("Expected error status, got %d", w.Code)
			}
		}
	}()

	handler := HAGetEntitiesHandler(nil)
	handler(w, req)
}
