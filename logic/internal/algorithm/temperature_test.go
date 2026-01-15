package algorithm

import (
	"testing"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

func TestCalculateMainTargetTemperature(t *testing.T) {
	tests := []struct {
		name           string
		zones          []models.ZoneState
		config         models.GlobalConfig
		currentTarget  float64
		expectedTarget float64
		shouldUpdate   bool
	}{
		{
			name: "Average mode with two zones",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 22.0, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  19.0,
			expectedTarget: 21.0,
			shouldUpdate:   true,
		},
		{
			name: "Exclude overheated zones",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
				{ID: "zone2", Enabled: true, TargetTemperature: 25.0, Satisfaction: "overheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  19.0,
			expectedTarget: 20.0,
			shouldUpdate:   true,
		},
		{
			name: "No update when below threshold",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, TargetTemperature: 20.0, Satisfaction: "underheated"},
			},
			config: models.GlobalConfig{
				UseAverageMode:      true,
				MainMinTemp:         15.0,
				MainMaxTemp:         30.0,
				MainChangeThreshold: 0.5,
			},
			currentTarget:  20.2,
			expectedTarget: 0,
			shouldUpdate:   false,
		},
		{
			name:           "No active zones",
			zones:          []models.ZoneState{},
			config:         models.GlobalConfig{},
			currentTarget:  20.0,
			expectedTarget: 0,
			shouldUpdate:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			target, shouldUpdate := CalculateMainTargetTemperature(tt.zones, tt.config, tt.currentTarget)
			
			if shouldUpdate != tt.shouldUpdate {
				t.Errorf("shouldUpdate = %v, want %v", shouldUpdate, tt.shouldUpdate)
			}
			
			if shouldUpdate && target != tt.expectedTarget {
				t.Errorf("target = %v, want %v", target, tt.expectedTarget)
			}
		})
	}
}

func TestDetermineZoneSatisfaction(t *testing.T) {
	tests := []struct {
		name         string
		zone         models.ZoneState
		epsilon      float64
		expectedSat  string
	}{
		{
			name: "Underheated zone",
			zone: models.ZoneState{
				CurrentTemperature: 19.0,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "underheated",
		},
		{
			name: "Overheated zone",
			zone: models.ZoneState{
				CurrentTemperature: 23.0,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "overheated",
		},
		{
			name: "Satisfied zone",
			zone: models.ZoneState{
				CurrentTemperature: 22.0,
				TargetTemperature:  22.0,
				OpeningOffset:      0.3,
				ClosingOffset:      0.3,
			},
			epsilon:     0.0,
			expectedSat: "satisfied",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			satisfaction := DetermineZoneSatisfaction(tt.zone, tt.epsilon)
			if satisfaction != tt.expectedSat {
				t.Errorf("satisfaction = %v, want %v", satisfaction, tt.expectedSat)
			}
		})
	}
}

func TestCheckMinimumValves(t *testing.T) {
	tests := []struct {
		name            string
		zones           []models.ZoneState
		minValvesOpen   int
		expectedValves  int
	}{
		{
			name: "Sufficient valves open",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "open", IsFallbackValve: false},
				{ID: "zone2", Enabled: true, ValveState: "open", IsFallbackValve: false},
			},
			minValvesOpen:  1,
			expectedValves: 0,
		},
		{
			name: "Need to open fallback valve",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed", IsFallbackValve: true},
				{ID: "zone2", Enabled: true, ValveState: "closed", IsFallbackValve: false},
			},
			minValvesOpen:  1,
			expectedValves: 1,
		},
		{
			name: "Need to open multiple fallback valves",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed", IsFallbackValve: true},
				{ID: "zone2", Enabled: true, ValveState: "closed", IsFallbackValve: true},
			},
			minValvesOpen:  2,
			expectedValves: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valves := CheckMinimumValves(tt.zones, tt.minValvesOpen)
			if len(valves) != tt.expectedValves {
				t.Errorf("CheckMinimumValves returned %d valves, want %d", len(valves), tt.expectedValves)
			}
		})
	}
}
