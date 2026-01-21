package homeassistant

import (
	"context"
	"testing"
)

func TestNewIntegration(t *testing.T) {
	tests := []struct {
		name            string
		baseURL         string
		token           string
		expectedEnabled bool
	}{
		{
			name:            "Valid configuration",
			baseURL:         "http://homeassistant.local:8123",
			token:           "test_token",
			expectedEnabled: true,
		},
		{
			name:            "Empty base URL",
			baseURL:         "",
			token:           "test_token",
			expectedEnabled: false,
		},
		{
			name:            "Empty token",
			baseURL:         "http://homeassistant.local:8123",
			token:           "",
			expectedEnabled: false,
		},
		{
			name:            "Both empty",
			baseURL:         "",
			token:           "",
			expectedEnabled: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			integration := NewIntegration(tt.baseURL, tt.token)
			
			if integration == nil {
				t.Fatal("Expected integration to be non-nil")
			}
			
			if integration.IsEnabled() != tt.expectedEnabled {
				t.Errorf("IsEnabled() = %v, want %v", integration.IsEnabled(), tt.expectedEnabled)
			}
			
			if integration.baseURL != tt.baseURL {
				t.Errorf("baseURL = %v, want %v", integration.baseURL, tt.baseURL)
			}
			
			if integration.token != tt.token {
				t.Errorf("token = %v, want %v", integration.token, tt.token)
			}
		})
	}
}

func TestSetMainTemperature(t *testing.T) {
	tests := []struct {
		name        string
		enabled     bool
		entityID    string
		temperature float64
		expectError bool
	}{
		{
			name:        "Enabled integration",
			enabled:     true,
			entityID:    "climate.main_thermostat",
			temperature: 21.5,
			expectError: false,
		},
		{
			name:        "Disabled integration",
			enabled:     false,
			entityID:    "climate.main_thermostat",
			temperature: 21.5,
			expectError: true,
		},
		{
			name:        "Main climate precision 0.5°C",
			enabled:     true,
			entityID:    "climate.main_thermostat",
			temperature: 22.0,
			expectError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var integration *Integration
			if tt.enabled {
				integration = NewIntegration("http://homeassistant.local:8123", "test_token")
			} else {
				integration = NewIntegration("", "")
			}
			
			ctx := context.Background()
			err := integration.SetMainTemperature(ctx, tt.entityID, tt.temperature)
			
			if (err != nil) != tt.expectError {
				t.Errorf("SetMainTemperature() error = %v, expectError = %v", err, tt.expectError)
			}
		})
	}
}

func TestSetValveState(t *testing.T) {
	tests := []struct {
		name        string
		enabled     bool
		entityID    string
		open        bool
		expectError bool
	}{
		{
			name:        "Open valve - enabled",
			enabled:     true,
			entityID:    "switch.bedroom_valve",
			open:        true,
			expectError: false,
		},
		{
			name:        "Close valve - enabled",
			enabled:     true,
			entityID:    "switch.bedroom_valve",
			open:        false,
			expectError: false,
		},
		{
			name:        "Disabled integration",
			enabled:     false,
			entityID:    "switch.bedroom_valve",
			open:        true,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var integration *Integration
			if tt.enabled {
				integration = NewIntegration("http://homeassistant.local:8123", "test_token")
			} else {
				integration = NewIntegration("", "")
			}
			
			ctx := context.Background()
			err := integration.SetValveState(ctx, tt.entityID, tt.open)
			
			if (err != nil) != tt.expectError {
				t.Errorf("SetValveState() error = %v, expectError = %v", err, tt.expectError)
			}
		})
	}
}

func TestGetTemperature(t *testing.T) {
	tests := []struct {
		name        string
		enabled     bool
		entityID    string
		expectError bool
	}{
		{
			name:        "Read temperature - enabled",
			enabled:     true,
			entityID:    "sensor.bedroom_temperature",
			expectError: false,
		},
		{
			name:        "Disabled integration",
			enabled:     false,
			entityID:    "sensor.bedroom_temperature",
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var integration *Integration
			if tt.enabled {
				integration = NewIntegration("http://homeassistant.local:8123", "test_token")
			} else {
				integration = NewIntegration("", "")
			}
			
			ctx := context.Background()
			_, err := integration.GetTemperature(ctx, tt.entityID)
			
			if (err != nil) != tt.expectError {
				t.Errorf("GetTemperature() error = %v, expectError = %v", err, tt.expectError)
			}
		})
	}
}

func TestSetZoneTemperature(t *testing.T) {
	tests := []struct {
		name        string
		enabled     bool
		entityID    string
		temperature float64
		expectError bool
	}{
		{
			name:        "Zone temperature with 0.1°C precision",
			enabled:     true,
			entityID:    "climate.zone_bedroom",
			temperature: 21.1,
			expectError: false,
		},
		{
			name:        "Zone temperature 0.5°C",
			enabled:     true,
			entityID:    "climate.zone_bedroom",
			temperature: 21.5,
			expectError: false,
		},
		{
			name:        "Disabled integration",
			enabled:     false,
			entityID:    "climate.zone_bedroom",
			temperature: 21.1,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var integration *Integration
			if tt.enabled {
				integration = NewIntegration("http://homeassistant.local:8123", "test_token")
			} else {
				integration = NewIntegration("", "")
			}
			
			ctx := context.Background()
			err := integration.SetZoneTemperature(ctx, tt.entityID, tt.temperature)
			
			if (err != nil) != tt.expectError {
				t.Errorf("SetZoneTemperature() error = %v, expectError = %v", err, tt.expectError)
			}
		})
	}
}

func TestSetZoneEnabled(t *testing.T) {
	tests := []struct {
		name        string
		integrationEnabled bool
		entityID    string
		zoneEnabled bool
		expectError bool
	}{
		{
			name:        "Enable zone",
			integrationEnabled: true,
			entityID:    "climate.zone_bedroom",
			zoneEnabled: true,
			expectError: false,
		},
		{
			name:        "Disable zone",
			integrationEnabled: true,
			entityID:    "climate.zone_bedroom",
			zoneEnabled: false,
			expectError: false,
		},
		{
			name:        "Disabled integration",
			integrationEnabled: false,
			entityID:    "climate.zone_bedroom",
			zoneEnabled: true,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var integration *Integration
			if tt.integrationEnabled {
				integration = NewIntegration("http://homeassistant.local:8123", "test_token")
			} else {
				integration = NewIntegration("", "")
			}
			
			ctx := context.Background()
			err := integration.SetZoneEnabled(ctx, tt.entityID, tt.zoneEnabled)
			
			if (err != nil) != tt.expectError {
				t.Errorf("SetZoneEnabled() error = %v, expectError = %v", err, tt.expectError)
			}
		})
	}
}

func TestGetZoneHVACAction(t *testing.T) {
	tests := []struct {
		name         string
		entityID     string
		valveOpen    bool
		expectedAction string
	}{
		{
			name:         "Valve closed - idle",
			entityID:     "climate.zone_bedroom",
			valveOpen:    false,
			expectedAction: "idle",
		},
		{
			name:         "Valve open - heating",
			entityID:     "climate.zone_bedroom",
			valveOpen:    true,
			expectedAction: "heating",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			integration := NewIntegration("http://homeassistant.local:8123", "test_token")
			ctx := context.Background()
			
			action := integration.GetZoneHVACAction(ctx, tt.entityID, tt.valveOpen)
			
			if action != tt.expectedAction {
				t.Errorf("GetZoneHVACAction() = %v, want %v", action, tt.expectedAction)
			}
		})
	}
}
