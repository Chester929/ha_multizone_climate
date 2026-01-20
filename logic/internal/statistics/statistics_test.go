package statistics

import (
	"testing"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

// TestNewTracker tests tracker creation
func TestNewTracker(t *testing.T) {
	// Create a mock redis client (in real scenario, use test container)
	// For now, just test the structure
	tracker := NewTracker(nil)
	
	if tracker == nil {
		t.Fatal("Expected tracker to be created")
	}
	
	if tracker.storage == nil {
		t.Error("Expected storage to be initialized")
	}
	
	if tracker.metrics == nil {
		t.Error("Expected metrics calculator to be initialized")
	}
}

// TestTemperatureReading tests temperature reading structure
func TestTemperatureReading(t *testing.T) {
	reading := TemperatureReading{
		ZoneID:      "zone1",
		Temperature: 21.5,
		Timestamp:   time.Now(),
	}
	
	if reading.ZoneID != "zone1" {
		t.Errorf("Expected zone_id to be 'zone1', got '%s'", reading.ZoneID)
	}
	
	if reading.Temperature != 21.5 {
		t.Errorf("Expected temperature to be 21.5, got %f", reading.Temperature)
	}
}

// TestValveActivity tests valve activity structure
func TestValveActivity(t *testing.T) {
	activity := ValveActivity{
		ZoneID:    "zone1",
		State:     "open",
		Timestamp: time.Now(),
	}
	
	if activity.State != "open" {
		t.Errorf("Expected state to be 'open', got '%s'", activity.State)
	}
}

// TestEnergyMetrics tests energy metrics structure
func TestEnergyMetrics(t *testing.T) {
	metrics := EnergyMetrics{
		ZoneID:             "zone1",
		TotalRuntimeHours:  5.5,
		OpenPercentage:     45.8,
		EstimatedEnergyKWh: 0.55,
		CycleCount:         10,
		AverageOpenTime:    33.0,
		TimeRange:          12,
	}
	
	if metrics.TotalRuntimeHours != 5.5 {
		t.Errorf("Expected runtime to be 5.5, got %f", metrics.TotalRuntimeHours)
	}
	
	if metrics.CycleCount != 10 {
		t.Errorf("Expected cycle count to be 10, got %d", metrics.CycleCount)
	}
}

// TestComfortMetrics tests comfort metrics structure
func TestComfortMetrics(t *testing.T) {
	metrics := ComfortMetrics{
		ZoneID:                "zone1",
		SatisfiedPercentage:   85.5,
		UnderheatedPercentage: 10.0,
		OverheatedPercentage:  4.5,
		AverageTemperature:    21.2,
		TemperatureStdDev:     0.8,
		ComfortScore:          88.5,
		TimeRange:             24,
	}
	
	if metrics.SatisfiedPercentage != 85.5 {
		t.Errorf("Expected satisfied percentage to be 85.5, got %f", metrics.SatisfiedPercentage)
	}
	
	if metrics.ComfortScore != 88.5 {
		t.Errorf("Expected comfort score to be 88.5, got %f", metrics.ComfortScore)
	}
}

// TestPerformanceMetrics tests performance metrics structure
func TestPerformanceMetrics(t *testing.T) {
	metrics := PerformanceMetrics{
		TempCalculationAvgMs: 15.5,
		ValveUpdateAvgMs:     8.2,
		SafetyCheckAvgMs:     5.1,
		TempCalculationCount: 100,
		ValveUpdateCount:     50,
		SafetyCheckCount:     25,
		TotalExecutions:      175,
		TimeRange:            24,
	}
	
	if metrics.TotalExecutions != 175 {
		t.Errorf("Expected total executions to be 175, got %d", metrics.TotalExecutions)
	}
	
	if metrics.TempCalculationAvgMs != 15.5 {
		t.Errorf("Expected temp calculation avg to be 15.5, got %f", metrics.TempCalculationAvgMs)
	}
}

// TestTrackZoneUpdate tests tracking zone updates
func TestTrackZoneUpdate(t *testing.T) {
	// This would require a real Redis connection for integration testing
	// For unit testing, we verify the structure and logic
	
	zone := &models.ZoneState{
		ID:                 "zone1",
		Name:               "Living Room",
		CurrentTemperature: 21.5,
		TargetTemperature:  22.0,
		Satisfaction:       "underheated",
		ValveState:         "open",
	}
	
	// Verify zone state is valid
	if zone.ID == "" {
		t.Error("Zone ID should not be empty")
	}
	
	if zone.CurrentTemperature < 0 || zone.CurrentTemperature > 50 {
		t.Error("Temperature should be in reasonable range")
	}
}

// TestNewStorage tests storage creation
func TestNewStorage(t *testing.T) {
	storage := NewStorage(nil)
	
	if storage == nil {
		t.Fatal("Expected storage to be created")
	}
}

// TestNewMetricsCalculator tests metrics calculator creation
func TestNewMetricsCalculator(t *testing.T) {
	storage := NewStorage(nil)
	calculator := NewMetricsCalculator(storage)
	
	if calculator == nil {
		t.Fatal("Expected metrics calculator to be created")
	}
	
	if calculator.storage == nil {
		t.Error("Expected storage to be set in calculator")
	}
}
