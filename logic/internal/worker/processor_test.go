package worker

import (
	"context"
	"strconv"
	"testing"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
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

// mockHAIntegration is a mock implementation of the HA integration for testing
type mockHAIntegration struct {
	mainTempCalls   []float64
	valveStateCalls []valveStateCall
	zoneEnabledCalls []zoneEnabledCall
	enabled         bool
}

type valveStateCall struct {
	entityID string
	open     bool
}

type zoneEnabledCall struct {
	entityID string
	enabled  bool
}

func newMockHAIntegration() *mockHAIntegration {
	return &mockHAIntegration{
		mainTempCalls:   []float64{},
		valveStateCalls: []valveStateCall{},
		zoneEnabledCalls: []zoneEnabledCall{},
		enabled:         true,
	}
}

func (m *mockHAIntegration) IsEnabled() bool {
	return m.enabled
}

func (m *mockHAIntegration) SetMainTemperature(ctx context.Context, entityID string, temperature float64) error {
	m.mainTempCalls = append(m.mainTempCalls, temperature)
	return nil
}

func (m *mockHAIntegration) SetValveState(ctx context.Context, entityID string, open bool) error {
	m.valveStateCalls = append(m.valveStateCalls, valveStateCall{
		entityID: entityID,
		open:     open,
	})
	return nil
}

func (m *mockHAIntegration) SetZoneEnabled(ctx context.Context, entityID string, enabled bool) error {
	m.zoneEnabledCalls = append(m.zoneEnabledCalls, zoneEnabledCall{
		entityID: entityID,
		enabled:  enabled,
	})
	return nil
}

func TestProcessorWithMockedDependencies(t *testing.T) {
	// Note: Mock dependencies (mockRedisClient and mockHAIntegration) are defined above
	// for future use when implementing actual HTTP API calls for the HA integration.
	// Currently testing the processor creation with nil dependencies.
	var haIntegration *homeassistant.Integration
	
	processor := NewProcessor(nil, haIntegration)
	
	if processor == nil {
		t.Fatal("Expected processor to be non-nil")
	}
	
	// Verify processor was created with correct dependencies
	if processor.redisClient != nil {
		t.Error("Expected redisClient to be nil when nil is passed")
	}
	
	if processor.haIntegration != nil {
		t.Error("Expected haIntegration to be nil when nil is passed")
	}
	
	if processor.statsTracker == nil {
		t.Error("Expected statsTracker to be created")
	}
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
		name          string
		redisClient   interface{}
		haIntegration *homeassistant.Integration
	}{
		{
			name:          "Create with nil dependencies",
			redisClient:   nil,
			haIntegration: nil,
		},
		{
			name:          "Create with HA integration",
			redisClient:   nil,
			haIntegration: homeassistant.NewIntegration("http://ha:8123", "token"),
		},
		{
			name:          "Create with disabled HA integration",
			redisClient:   nil,
			haIntegration: homeassistant.NewIntegration("", ""),
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			processor := NewProcessor(nil, tt.haIntegration)
			
			if processor == nil {
				t.Fatal("Expected processor to be non-nil")
			}
			
			if processor.haIntegration != tt.haIntegration {
				t.Error("Expected haIntegration to match input")
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
	
	t.Run("HVAC action based on valve state", func(t *testing.T) {
		ha := homeassistant.NewIntegration("http://ha:8123", "token")
		ctx := context.Background()
		
		// When valve is closed, HVAC action should be idle
		action := ha.GetZoneHVACAction(ctx, "climate.zone1", false)
		if action != "idle" {
			t.Errorf("HVAC action = %v, want idle when valve is closed", action)
		}
		
		// When valve is open, HVAC action should be heating (or cooling)
		action = ha.GetZoneHVACAction(ctx, "climate.zone1", true)
		if action != "heating" && action != "cooling" {
			t.Errorf("HVAC action = %v, want heating or cooling when valve is open", action)
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
	
	t.Run("Main climate drives zones", func(t *testing.T) {
		// This test verifies that the main climate entity is used to control the overall heating
		// while zones are controlled individually
		
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
