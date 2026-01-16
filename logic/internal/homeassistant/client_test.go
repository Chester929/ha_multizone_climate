package homeassistant

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// TestNewClient tests client creation
func TestNewClient(t *testing.T) {
	client := NewClient("http://test.local:8123", "test-token")
	if client == nil {
		t.Fatal("Expected client to be created")
	}
	if client.baseURL != "http://test.local:8123" {
		t.Errorf("Expected baseURL to be 'http://test.local:8123', got '%s'", client.baseURL)
	}
	if client.token != "test-token" {
		t.Errorf("Expected token to be 'test-token', got '%s'", client.token)
	}
}

// TestGetState tests getting entity state
func TestGetState(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify authorization header
		auth := r.Header.Get("Authorization")
		if auth != "Bearer test-token" {
			t.Errorf("Expected Authorization header 'Bearer test-token', got '%s'", auth)
		}

		// Verify path
		expectedPath := "/api/states/sensor.temperature"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		// Return mock state
		state := EntityState{
			EntityID: "sensor.temperature",
			State:    "21.5",
			Attributes: map[string]interface{}{
				"unit_of_measurement": "°C",
				"device_class":        "temperature",
			},
			LastChanged: time.Now().Format(time.RFC3339),
			LastUpdated: time.Now().Format(time.RFC3339),
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(state)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	state, err := client.GetState(ctx, "sensor.temperature")
	if err != nil {
		t.Fatalf("GetState failed: %v", err)
	}

	if state.EntityID != "sensor.temperature" {
		t.Errorf("Expected entity_id 'sensor.temperature', got '%s'", state.EntityID)
	}

	if state.State != "21.5" {
		t.Errorf("Expected state '21.5', got '%s'", state.State)
	}

	if state.Attributes["unit_of_measurement"] != "°C" {
		t.Errorf("Expected unit_of_measurement '°C', got '%v'", state.Attributes["unit_of_measurement"])
	}
}

// TestGetStates tests getting all states
func TestGetStates(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/states"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		states := []EntityState{
			{
				EntityID: "sensor.temp1",
				State:    "20.5",
			},
			{
				EntityID: "sensor.temp2",
				State:    "22.0",
			},
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(states)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	states, err := client.GetStates(ctx)
	if err != nil {
		t.Fatalf("GetStates failed: %v", err)
	}

	if len(states) != 2 {
		t.Errorf("Expected 2 states, got %d", len(states))
	}

	if states[0].EntityID != "sensor.temp1" {
		t.Errorf("Expected first entity 'sensor.temp1', got '%s'", states[0].EntityID)
	}
}

// TestCallService tests calling a service
func TestCallService(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/services/switch/turn_on"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		if r.Method != "POST" {
			t.Errorf("Expected POST method, got '%s'", r.Method)
		}

		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("Failed to decode request body: %v", err)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.CallService(ctx, &ServiceCall{
		Domain:  "switch",
		Service: "turn_on",
		Target: &ServiceTarget{
			EntityID: "switch.valve1",
		},
	})

	if err != nil {
		t.Fatalf("CallService failed: %v", err)
	}
}

// TestTurnOnSwitch tests turning on a switch
func TestTurnOnSwitch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/services/switch/turn_on"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.TurnOnSwitch(ctx, "switch.valve1")
	if err != nil {
		t.Fatalf("TurnOnSwitch failed: %v", err)
	}
}

// TestTurnOffSwitch tests turning off a switch
func TestTurnOffSwitch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/services/switch/turn_off"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.TurnOffSwitch(ctx, "switch.valve1")
	if err != nil {
		t.Fatalf("TurnOffSwitch failed: %v", err)
	}
}

// TestSetTemperature tests setting climate temperature
func TestSetTemperature(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/services/climate/set_temperature"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("Failed to decode request body: %v", err)
		}

		serviceData, ok := body["service_data"].(map[string]interface{})
		if !ok {
			t.Fatal("Expected service_data in request body")
		}

		temp, ok := serviceData["temperature"].(float64)
		if !ok {
			t.Fatal("Expected temperature in service_data")
		}

		if temp != 22.5 {
			t.Errorf("Expected temperature 22.5, got %f", temp)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.SetTemperature(ctx, "climate.main", 22.5)
	if err != nil {
		t.Fatalf("SetTemperature failed: %v", err)
	}
}

// TestSetHVACMode tests setting HVAC mode
func TestSetHVACMode(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/services/climate/set_hvac_mode"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("Failed to decode request body: %v", err)
		}

		serviceData, ok := body["service_data"].(map[string]interface{})
		if !ok {
			t.Fatal("Expected service_data in request body")
		}

		mode, ok := serviceData["hvac_mode"].(string)
		if !ok {
			t.Fatal("Expected hvac_mode in service_data")
		}

		if mode != "heat" {
			t.Errorf("Expected hvac_mode 'heat', got '%s'", mode)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.SetHVACMode(ctx, "climate.main", "heat")
	if err != nil {
		t.Fatalf("SetHVACMode failed: %v", err)
	}
}

// TestPing tests the ping functionality
func TestPing(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := "/api/"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected path '%s', got '%s'", expectedPath, r.URL.Path)
		}

		auth := r.Header.Get("Authorization")
		if auth != "Bearer test-token" {
			t.Errorf("Expected Authorization header 'Bearer test-token', got '%s'", auth)
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"message": "API running."})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.Ping(ctx)
	if err != nil {
		t.Fatalf("Ping failed: %v", err)
	}
}

// TestGetStateError tests error handling
func TestGetStateError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]string{"error": "Entity not found"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	_, err := client.GetState(ctx, "sensor.nonexistent")
	if err == nil {
		t.Fatal("Expected error for non-existent entity")
	}
}

// TestCallServiceError tests service call error handling
func TestCallServiceError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid service call"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	ctx := context.Background()

	err := client.CallService(ctx, &ServiceCall{
		Domain:  "invalid",
		Service: "invalid",
	})

	if err == nil {
		t.Fatal("Expected error for invalid service call")
	}
}
