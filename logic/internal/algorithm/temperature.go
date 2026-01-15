package algorithm

import (
	"math"
	"slices"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

// CalculateMainTargetTemperature calculates the main thermostat target temperature
// based on all zone states and configuration
func CalculateMainTargetTemperature(zones []models.ZoneState, config models.GlobalConfig, currentTarget float64) (float64, bool) {
	// Filter active zones (enabled and not overheated)
	var activeZones []models.ZoneState
	for _, z := range zones {
		if z.Enabled && z.Satisfaction != "overheated" {
			activeZones = append(activeZones, z)
		}
	}

	// If no active zones, no update needed
	if len(activeZones) == 0 {
		return 0, false
	}

	var rawTarget float64

	if config.UseAverageMode {
		// Average mode: average of all target temperatures
		sum := 0.0
		for _, z := range activeZones {
			sum += z.TargetTemperature
		}
		rawTarget = sum / float64(len(activeZones))
	} else {
		// Slider mode: interpolate between min and max targets
		targets := make([]float64, len(activeZones))
		for i, z := range activeZones {
			targets[i] = z.TargetTemperature
		}
		minTarget := slices.Min(targets)
		maxTarget := slices.Max(targets)
		
		// Use configured slider position (default to 0.5 if not set)
		sliderPos := config.SliderPosition
		if sliderPos < 0 || sliderPos > 1 {
			sliderPos = 0.5 // Default to middle if invalid
		}
		rawTarget = minTarget + sliderPos*(maxTarget-minTarget)
	}

	// Round to 0.5°C
	rounded := math.Round(rawTarget*2) / 2

	// Clamp to min/max
	clamped := math.Max(config.MainMinTemp, math.Min(config.MainMaxTemp, rounded))

	// Check if change exceeds threshold
	if math.Abs(clamped-currentTarget) < config.MainChangeThreshold {
		return 0, false
	}

	return clamped, true
}

// DetermineZoneSatisfaction determines the satisfaction state of a zone
func DetermineZoneSatisfaction(zone models.ZoneState, epsilon float64) string {
	diff := zone.CurrentTemperature - zone.TargetTemperature

	if diff < -zone.OpeningOffset-epsilon {
		return "underheated"
	} else if diff > zone.ClosingOffset+epsilon {
		return "overheated"
	}
	return "satisfied"
}

// ShouldOpenValve determines if a valve should be opened
func ShouldOpenValve(zone models.ZoneState) bool {
	return zone.Satisfaction == "underheated" && zone.ValveState != "open"
}

// ShouldCloseValve determines if a valve should be closed
func ShouldCloseValve(zone models.ZoneState) bool {
	return (zone.Satisfaction == "overheated" || zone.Satisfaction == "satisfied") && zone.ValveState != "closed"
}

// CheckMinimumValves checks if minimum valves are open and returns valves to force open if needed
func CheckMinimumValves(zones []models.ZoneState, minValvesOpen int) []string {
	openCount := 0
	fallbackValves := []string{}

	// Count currently open valves
	for _, z := range zones {
		if z.Enabled && z.ValveState == "open" {
			openCount++
		}
		if z.Enabled && z.IsFallbackValve {
			fallbackValves = append(fallbackValves, z.ID)
		}
	}

	// If we have enough open valves, no action needed
	if openCount >= minValvesOpen {
		return []string{}
	}

	// Calculate how many valves we need to open
	shortage := minValvesOpen - openCount

	// Return the required number of fallback valves to open
	if len(fallbackValves) < shortage {
		return fallbackValves // Open all fallback valves if not enough
	}
	return fallbackValves[:shortage]
}
