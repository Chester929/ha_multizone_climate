package algorithm

import (
	"math"
	"testing"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

// TestCalculateMainTargetTemperaturePrecision tests that main climate temperature
// is always rounded to 0.5°C precision as specified in requirements
func TestCalculateMainTargetTemperaturePrecision(t *testing.T) {
	tests := []struct {
		name           string
		zones          []models.ZoneState
		config         models.GlobalConfig
		currentTarget  float64
		expectedTarget float64
		shouldUpdate   bool
		description    string
	}{
		{
			name: "Main climate precision - round to 0.5°C (21.25 -> 21.5)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 21.2, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 21.3, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  19.0,
			expectedTarget: 21.5, // Average is 21.25, rounded to 21.5
			shouldUpdate:   true,
			description:    "Main climate must use 0.5°C precision",
		},
		{
			name: "Main climate precision - round to 0.5°C (20.75 -> 21.0)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.7, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 20.8, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  19.0,
			expectedTarget: 21.0, // Average is 20.75, rounded to 21.0
			shouldUpdate:   true,
			description:    "Main climate must use 0.5°C precision",
		},
		{
			name: "Main climate precision - round to 0.5°C (20.24 -> 20.0)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.1, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 20.3, Satisfaction: "underheated"},
				{ID: "zone3", Enabled: true, TargetTemperature: 20.3, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  19.0,
			expectedTarget: 20.0, // Average is 20.233, rounded to 20.0
			shouldUpdate:   true,
			description:    "Main climate must use 0.5°C precision",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			target, shouldUpdate := CalculateMainTargetTemperature(tt.zones, tt.config, tt.currentTarget)

			if shouldUpdate != tt.shouldUpdate {
				t.Errorf("shouldUpdate = %v, want %v", shouldUpdate, tt.shouldUpdate)
			}

			if shouldUpdate {
				if target != tt.expectedTarget {
					t.Errorf("target = %v, want %v (description: %s)", target, tt.expectedTarget, tt.description)
				}
				// Verify precision is 0.5°C
				remainder := math.Mod(target, 0.5)
				if math.Abs(remainder) > 0.001 {
					t.Errorf("target %v is not a multiple of 0.5°C (remainder: %v)", target, remainder)
				}
			}
		})
	}
}

// TestCalculateMainTargetTemperatureSliderMode tests slider mode with various positions
func TestCalculateMainTargetTemperatureSliderMode(t *testing.T) {
	tests := []struct {
		name           string
		zones          []models.ZoneState
		sliderPosition float64
		expectedTarget float64
		shouldUpdate   bool
	}{
		{
			name: "Slider mode - position 0.0 (minimum)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 18.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 24.0, Satisfaction: "underheated"},
			},
			sliderPosition: 0.0,
			expectedTarget: 18.0,
			shouldUpdate:   true,
		},
		{
			name: "Slider mode - position 1.0 (maximum)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 18.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 24.0, Satisfaction: "underheated"},
			},
			sliderPosition: 1.0,
			expectedTarget: 24.0,
			shouldUpdate:   true,
		},
		{
			name: "Slider mode - position 0.5 (middle)",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 18.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 24.0, Satisfaction: "underheated"},
			},
			sliderPosition: 0.5,
			expectedTarget: 21.0, // 18 + 0.5 * (24-18) = 21
			shouldUpdate:   true,
		},
		{
			name: "Slider mode - position 0.25",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 24.0, Satisfaction: "underheated"},
			},
			sliderPosition: 0.25,
			expectedTarget: 21.0, // 20 + 0.25 * (24-20) = 21
			shouldUpdate:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := models.GlobalConfig{
				UseAverageMode:      false,
				SliderPosition:      tt.sliderPosition,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			}

			target, shouldUpdate := CalculateMainTargetTemperature(tt.zones, config, 19.0)

			if shouldUpdate != tt.shouldUpdate {
				t.Errorf("shouldUpdate = %v, want %v", shouldUpdate, tt.shouldUpdate)
			}

			if shouldUpdate && target != tt.expectedTarget {
				t.Errorf("target = %v, want %v", target, tt.expectedTarget)
			}
		})
	}
}

// TestCalculateMainTargetTemperatureBoundaryConditions tests min/max temperature clamping
func TestCalculateMainTargetTemperatureBoundaryConditions(t *testing.T) {
	tests := []struct {
		name           string
		zones          []models.ZoneState
		config         models.GlobalConfig
		expectedTarget float64
		shouldUpdate   bool
	}{
		{
			name: "Clamp to minimum temperature",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 10.0, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			expectedTarget: 15.0, // Clamped to minimum
			shouldUpdate:   true,
		},
		{
			name: "Clamp to maximum temperature",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 35.0, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			expectedTarget: 30.0, // Clamped to maximum
			shouldUpdate:   true,
		},
		{
			name: "Within range - no clamping",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 22.0, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			expectedTarget: 22.0,
			shouldUpdate:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			target, shouldUpdate := CalculateMainTargetTemperature(tt.zones, tt.config, 19.0)

			if shouldUpdate != tt.shouldUpdate {
				t.Errorf("shouldUpdate = %v, want %v", shouldUpdate, tt.shouldUpdate)
			}

			if shouldUpdate && target != tt.expectedTarget {
				t.Errorf("target = %v, want %v", target, tt.expectedTarget)
			}
		})
	}
}

// TestCalculateMainTargetTemperatureDisabledZones tests handling of disabled zones
func TestCalculateMainTargetTemperatureDisabledZones(t *testing.T) {
	tests := []struct {
		name           string
		zones          []models.ZoneState
		expectedTarget float64
		shouldUpdate   bool
	}{
		{
			name: "Ignore disabled zones",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: false, TargetTemperature: 30.0, Satisfaction: "underheated"},
			},
			expectedTarget: 20.0, // Only zone1 is counted
			shouldUpdate:   true,
		},
		{
			name: "All zones disabled",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: false, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: false, TargetTemperature: 30.0, Satisfaction: "underheated"},
			},
			expectedTarget: 0,
			shouldUpdate:   false,
		},
		{
			name: "Mix of enabled and disabled zones",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: false, TargetTemperature: 25.0, Satisfaction: "underheated"},
				{ID: "zone3", Enabled: true, TargetTemperature: 22.0, Satisfaction: "underheated"},
			},
			expectedTarget: 21.0, // Average of zone1 and zone3
			shouldUpdate:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			}

			target, shouldUpdate := CalculateMainTargetTemperature(tt.zones, config, 19.0)

			if shouldUpdate != tt.shouldUpdate {
				t.Errorf("shouldUpdate = %v, want %v", shouldUpdate, tt.shouldUpdate)
			}

			if shouldUpdate && target != tt.expectedTarget {
				t.Errorf("target = %v, want %v", target, tt.expectedTarget)
			}
		})
	}
}

// TestDetermineZoneSatisfactionEdgeCases tests edge cases in satisfaction determination
func TestDetermineZoneSatisfactionEdgeCases(t *testing.T) {
	tests := []struct {
		name        string
		zone        models.ZoneState
		epsilon     float64
		expectedSat string
	}{
		{
			name: "Exactly at target",
			zone: models.ZoneState{
				CurrentTemperature: 22.0,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "satisfied",
		},
		{
			name: "Slightly below target (within opening offset)",
			zone: models.ZoneState{
				CurrentTemperature: 21.9,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "satisfied",
		},
		{
			name: "Below opening threshold",
			zone: models.ZoneState{
				CurrentTemperature: 21.5,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "underheated",
		},
		{
			name: "Above closing threshold",
			zone: models.ZoneState{
				CurrentTemperature: 22.5,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "overheated",
		},
		{
			name: "With epsilon - just satisfied",
			zone: models.ZoneState{
				CurrentTemperature: 21.69,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.01,
			expectedSat: "satisfied",
		},
		{
			name: "With epsilon - underheated",
			zone: models.ZoneState{
				CurrentTemperature: 21.68,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.01,
			expectedSat: "underheated",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			satisfaction := DetermineZoneSatisfaction(tt.zone, tt.epsilon)
			if satisfaction != tt.expectedSat {
				t.Errorf("satisfaction = %v, want %v (current=%v, target=%v, opening=%v, closing=%v, epsilon=%v)",
					satisfaction, tt.expectedSat,
					tt.zone.CurrentTemperature, tt.zone.TargetTemperature,
					tt.zone.OpeningOffset, tt.zone.ClosingOffset, tt.epsilon)
			}
		})
	}
}

// TestShouldOpenValve tests valve opening conditions
func TestShouldOpenValve(t *testing.T) {
	tests := []struct {
		name         string
		zone         models.ZoneState
		expectedOpen bool
	}{
		{
			name: "Underheated zone with closed valve - should open",
			zone: models.ZoneState{
				Satisfaction: "underheated",
				ValveState:   "closed",
			},
			expectedOpen: true,
		},
		{
			name: "Underheated zone with already open valve - should not open",
			zone: models.ZoneState{
				Satisfaction: "underheated",
				ValveState:   "open",
			},
			expectedOpen: false,
		},
		{
			name: "Satisfied zone - should not open",
			zone: models.ZoneState{
				Satisfaction: "satisfied",
				ValveState:   "closed",
			},
			expectedOpen: false,
		},
		{
			name: "Overheated zone - should not open",
			zone: models.ZoneState{
				Satisfaction: "overheated",
				ValveState:   "closed",
			},
			expectedOpen: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shouldOpen := ShouldOpenValve(tt.zone)
			if shouldOpen != tt.expectedOpen {
				t.Errorf("ShouldOpenValve() = %v, want %v", shouldOpen, tt.expectedOpen)
			}
		})
	}
}

// TestShouldCloseValve tests valve closing conditions
func TestShouldCloseValve(t *testing.T) {
	tests := []struct {
		name          string
		zone          models.ZoneState
		expectedClose bool
	}{
		{
			name: "Overheated zone with open valve - should close",
			zone: models.ZoneState{
				Satisfaction: "overheated",
				ValveState:   "open",
			},
			expectedClose: true,
		},
		{
			name: "Satisfied zone with open valve - should close",
			zone: models.ZoneState{
				Satisfaction: "satisfied",
				ValveState:   "open",
			},
			expectedClose: true,
		},
		{
			name: "Overheated zone with already closed valve - should not close",
			zone: models.ZoneState{
				Satisfaction: "overheated",
				ValveState:   "closed",
			},
			expectedClose: false,
		},
		{
			name: "Underheated zone - should not close",
			zone: models.ZoneState{
				Satisfaction: "underheated",
				ValveState:   "open",
			},
			expectedClose: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shouldClose := ShouldCloseValve(tt.zone)
			if shouldClose != tt.expectedClose {
				t.Errorf("ShouldCloseValve() = %v, want %v", shouldClose, tt.expectedClose)
			}
		})
	}
}
