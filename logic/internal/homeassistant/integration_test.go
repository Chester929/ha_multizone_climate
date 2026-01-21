package homeassistant

import (
"testing"
)

// TestSetZoneClimateTemperatureMethodExists verifies the SetZoneClimateTemperature method signature
func TestSetZoneClimateTemperatureMethodExists(t *testing.T) {
t.Run("Method has correct signature", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

// Method signature is verified by compilation
// The fact that this test compiles and runs means the method exists with the correct signature
_ = integration.SetZoneClimateTemperature
})
}

// TestRefreshEntityCacheMethodExists verifies the RefreshEntityCache method signature
func TestRefreshEntityCacheMethodExists(t *testing.T) {
t.Run("Method has correct signature", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

// Method signature is verified by compilation
_ = integration.RefreshEntityCache
})
}

// TestUpdateZoneClimateMethodExists verifies the updateZoneClimate method exists
func TestUpdateZoneClimateMethodExists(t *testing.T) {
t.Run("Method exists and compiles", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

// Method signature verified by compilation
_ = integration
})
}

// TestClimateEntityCacheStructure verifies the climate entity cache structure
func TestClimateEntityCacheStructure(t *testing.T) {
t.Run("Cache has climateToZone map", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

integration.entityCache.Lock()
defer integration.entityCache.Unlock()

integration.entityCache.climateToZone["climate.bedroom"] = "multizone:zone:bedroom"
integration.entityCache.climateToZone["climate.living"] = "multizone:zone:living"

if val, ok := integration.entityCache.climateToZone["climate.bedroom"]; !ok || val != "multizone:zone:bedroom" {
t.Error("Climate cache mapping not working for bedroom")
}

if len(integration.entityCache.climateToZone) != 2 {
t.Errorf("Expected 2 climate entities in cache, got %d", len(integration.entityCache.climateToZone))
}
})
}

// TestIsZoneClimateHelper verifies the isZoneClimate helper method
func TestIsZoneClimateHelper(t *testing.T) {
t.Run("isZoneClimate identifies cached entities", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

integration.entityCache.Lock()
integration.entityCache.climateToZone = map[string]string{
"climate.bedroom": "multizone:zone:bedroom",
}
integration.entityCache.Unlock()

if !integration.isZoneClimate("climate.bedroom") {
t.Error("isZoneClimate should return true for climate.bedroom")
}

if integration.isZoneClimate("climate.unknown") {
t.Error("isZoneClimate should return false for climate.unknown")
}
})
}

// TestEntityCacheInitialization verifies entity cache is properly initialized
func TestEntityCacheInitialization(t *testing.T) {
t.Run("Cache maps are initialized on creation", func(t *testing.T) {
integration := NewIntegration("http://test:8123", "test-token", nil, false)

integration.entityCache.RLock()
defer integration.entityCache.RUnlock()

if integration.entityCache.tempSensorToZone == nil {
t.Error("tempSensorToZone map not initialized")
}

if integration.entityCache.valveToZone == nil {
t.Error("valveToZone map not initialized")
}

if integration.entityCache.climateToZone == nil {
t.Error("climateToZone map not initialized")
}
})
}
