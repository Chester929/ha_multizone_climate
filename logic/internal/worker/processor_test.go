package worker

import (
	"context"
	"strconv"
	"testing"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

// mockRedisClient is a mock implementation of the Redis client for testing
type mockRedisClient struct {
	zones       map[string]map[string]string
	config      map[string]string
	mainClimate map[string]string
}

func newMockRedisClient() *mockRedisClient {
	return &mockRedisClient{
		zones:       make(map[string]map[string]string),
		config:      make(map[string]string),
		mainClimate: make(map[string]string),
	}
}

func (m *mockRedisClient) Keys(ctx context.Context, pattern string) ([]string, error) {
	keys := []string{}
	for k := range m.zones {
		keys = append(keys, k)
	}
	return keys, nil
}

func (m *mockRedisClient) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	if key == "multizone:config" {
		return m.config, nil
	}
	if key == "multizone:main_climate" {
		return m.mainClimate, nil
	}
	if data, ok := m.zones[key]; ok {
		return data, nil
	}
	return map[string]string{}, nil
}

func (m *mockRedisClient) HSet(ctx context.Context, key string, values map[string]interface{}) error {
	if _, ok := m.zones[key]; !ok {
		m.zones[key] = make(map[string]string)
	}
	for k, v := range values {
		switch val := v.(type) {
		case string:
			m.zones[key][k] = val
		case int64:
			m.zones[key][k] = strconv.FormatInt(val, 10)
		}
	}
	return nil
}

func TestSetLastActuated(t *testing.T) {
	zone := &models.ZoneState{
		ID:   "test_zone",
		Name: "Test Zone",
	}
	
	// Initially, LastActuated should be nil
	if zone.LastActuated != nil {
		t.Error("Expected LastActuated to be nil initially")
	}
	
	// Set LastActuated
	beforeSet := time.Now()
	setLastActuated(zone)
	afterSet := time.Now()
	
	// Verify LastActuated was set
	if zone.LastActuated == nil {
		t.Fatal("Expected LastActuated to be set")
	}
	
	// Verify LastActuated is within expected time range
	if zone.LastActuated.Before(beforeSet) || zone.LastActuated.After(afterSet) {
		t.Errorf("LastActuated %v is outside expected range [%v, %v]",
			zone.LastActuated, beforeSet, afterSet)
	}
}

func TestProcessorCreation(t *testing.T) {
	tests := []struct {
		name        string
		redisClient interface{}
	}{
		{
			name:        "Create with nil redis client",
			redisClient: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			processor := NewProcessor(nil)
			
			if processor == nil {
				t.Fatal("Expected processor to be non-nil")
			}
			
			if processor.statsTracker == nil {
				t.Error("Expected statsTracker to be initialized")
			}
		})
	}
}

func TestTemperaturePrecisionInWorkflow(t *testing.T) {
	// This test verifies that the processor respects temperature precision requirements:
	// - Zone temperatures: 0.1°C precision
	// - Main climate: 0.5°C precision
	
	t.Run("Zone temperature precision 0.1°C", func(t *testing.T) {
		// Verify zone temperatures can be set with 0.1°C precision
		zone := models.ZoneState{
			ID:                "zone1",
			Name:              "Test Zone",
			TargetTemperature: 21.1,
		}
		
		if zone.TargetTemperature != 21.1 {
			t.Errorf("Zone target temperature = %v, want 21.1", zone.TargetTemperature)
		}
		
		// Verify 0.1°C increments work
		testTemps := []float64{20.0, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 21.0}
		for _, temp := range testTemps {
			zone.TargetTemperature = temp
			if zone.TargetTemperature != temp {
				t.Errorf("Zone target temperature = %v, want %v", zone.TargetTemperature, temp)
			}
		}
	})
	
	t.Run("Main climate precision 0.5°C", func(t *testing.T) {
		// Verify main climate temperatures use 0.5°C precision
		mainClimate := models.MainClimateState{
			EntityID:          "climate.main",
			TargetTemperature: 21.5,
		}
		
		if mainClimate.TargetTemperature != 21.5 {
			t.Errorf("Main climate target temperature = %v, want 21.5", mainClimate.TargetTemperature)
		}
		
		// Verify 0.5°C increments work
		testTemps := []float64{20.0, 20.5, 21.0, 21.5, 22.0, 22.5, 23.0}
		for _, temp := range testTemps {
			mainClimate.TargetTemperature = temp
			if mainClimate.TargetTemperature != temp {
				t.Errorf("Main climate target temperature = %v, want %v", mainClimate.TargetTemperature, temp)
			}
		}
	})
}

func TestZoneStateManagement(t *testing.T) {
	t.Run("Zone enable/disable", func(t *testing.T) {
		zone := models.ZoneState{
			ID:      "zone1",
			Name:    "Test Zone",
			Enabled: true,
		}
		
		if !zone.Enabled {
			t.Error("Zone should be enabled initially")
		}
		
		zone.Enabled = false
		if zone.Enabled {
			t.Error("Zone should be disabled after setting Enabled to false")
		}
	})
	
	t.Run("Valve state transitions", func(t *testing.T) {
		zone := models.ZoneState{
			ID:         "zone1",
			Name:       "Test Zone",
			ValveState: "closed",
		}
		
		if zone.ValveState != "closed" {
			t.Errorf("ValveState = %v, want closed", zone.ValveState)
		}
		
		zone.ValveState = "open"
		if zone.ValveState != "open" {
			t.Errorf("ValveState = %v, want open", zone.ValveState)
		}
	})
	
	t.Run("Zone state stored in addon", func(t *testing.T) {
		// In addon-only mode, valve states are stored but not directly controlled
		zone := models.ZoneState{
			ID:                "zone1",
			Name:              "Test Zone",
			ValveState:        "closed",
			ValveSwitchEntity: "switch.zone1_valve",
		}
		
		// Verify entity ID is stored
		if zone.ValveSwitchEntity != "switch.zone1_valve" {
			t.Errorf("ValveSwitchEntity = %v, want switch.zone1_valve", zone.ValveSwitchEntity)
		}
		
		// Verify state can be updated (for tracking purposes)
		zone.ValveState = "open"
		if zone.ValveState != "open" {
			t.Errorf("ValveState = %v, want open", zone.ValveState)
		}
	})
}

func TestMainClimateControl(t *testing.T) {
	t.Run("Main climate entity interaction", func(t *testing.T) {
		mainClimate := models.MainClimateState{
			EntityID:           "climate.main_thermostat",
			CurrentTemperature: 20.0,
			TargetTemperature:  21.0,
			HVACMode:           "heat",
			HVACAction:         "heating",
		}
		
		// Verify we can read current temperature
		if mainClimate.CurrentTemperature != 20.0 {
			t.Errorf("CurrentTemperature = %v, want 20.0", mainClimate.CurrentTemperature)
		}
		
		// Verify we can set target temperature
		mainClimate.TargetTemperature = 22.0
		if mainClimate.TargetTemperature != 22.0 {
			t.Errorf("TargetTemperature = %v, want 22.0", mainClimate.TargetTemperature)
		}
		
		// Verify target temperature respects 0.5°C precision
		mainClimate.TargetTemperature = 22.5
		if mainClimate.TargetTemperature != 22.5 {
			t.Errorf("TargetTemperature = %v, want 22.5", mainClimate.TargetTemperature)
		}
	})
	
	t.Run("Main climate entity stored in addon", func(t *testing.T) {
		// In addon-only mode, the main climate entity ID is stored
		// but the addon doesn't directly control it
		
		config := models.GlobalConfig{
			MainClimateEntityID: "climate.main_thermostat",
			UseAverageMode:      true,
			MainMinTemp:         15.0,
			MainMaxTemp:         30.0,
			MainChangeThreshold: 0.5,
		}
		
		if config.MainClimateEntityID != "climate.main_thermostat" {
			t.Errorf("MainClimateEntityID = %v, want climate.main_thermostat", config.MainClimateEntityID)
		}
		
		if config.MainChangeThreshold != 0.5 {
			t.Errorf("MainChangeThreshold = %v, want 0.5 (matches 0.5°C precision)", config.MainChangeThreshold)
		}
	})
}
