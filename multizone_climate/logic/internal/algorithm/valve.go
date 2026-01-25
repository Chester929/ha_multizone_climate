package algorithm

import (
	"slices"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

// ValveOperation represents a valve operation to be performed
type ValveOperation struct {
	ZoneID    string
	Operation string // "open" or "close"
	Priority  int
}

// CanActuateValve checks if a valve can be actuated based on timing constraints
func CanActuateValve(zone models.ZoneState, actuationDelay int) bool {
	// If valve has never been actuated, allow actuation
	if zone.LastActuated == nil {
		return true
	}

	// Check if enough time has passed since last actuation
	delayDuration := time.Duration(actuationDelay) * time.Second
	timeSinceLastActuation := time.Since(*zone.LastActuated)

	return timeSinceLastActuation >= delayDuration
}

// IsValveLocked checks if a valve is currently locked
func IsValveLocked(zone models.ZoneState) bool {
	if zone.ValveLockExpiration == nil {
		return false
	}

	// Check if lock has expired
	return time.Now().Before(*zone.ValveLockExpiration)
}

// LockValve creates a lock on a valve that expires after the specified duration
func LockValve(zone *models.ZoneState, lockDuration time.Duration) {
	expiration := time.Now().Add(lockDuration)
	zone.ValveLockExpiration = &expiration
}

// UnlockValve removes a lock from a valve
func UnlockValve(zone *models.ZoneState) {
	zone.ValveLockExpiration = nil
}

// SortZonesByPriority sorts zones by priority (higher priority first)
// If priorities are equal, sorts by zone ID for consistent ordering
func SortZonesByPriority(zones []models.ZoneState) []models.ZoneState {
	sorted := make([]models.ZoneState, len(zones))
	copy(sorted, zones)

	slices.SortFunc(sorted, func(a, b models.ZoneState) int {
		// Higher priority comes first (descending order)
		if a.Priority != b.Priority {
			return b.Priority - a.Priority
		}
		// If priorities are equal, sort by ID for consistency
		if a.ID < b.ID {
			return -1
		} else if a.ID > b.ID {
			return 1
		}
		return 0
	})

	return sorted
}

// CheckMinimumValvesByPriority checks if minimum valves are open and returns
// valves to force open if needed, selecting by priority
func CheckMinimumValvesByPriority(zones []models.ZoneState, minValvesOpen int) []string {
	openCount := 0
	fallbackValves := []models.ZoneState{}

	// Count currently open valves and collect closed fallback candidates
	for _, z := range zones {
		if z.Enabled && z.ValveState == "open" {
			openCount++
		}
		// Only collect fallback valves that are currently closed
		if z.Enabled && z.IsFallbackValve && z.ValveState != "open" {
			fallbackValves = append(fallbackValves, z)
		}
	}

	// If we have enough open valves, no action needed
	if openCount >= minValvesOpen {
		return []string{}
	}

	// Sort fallback valves by priority
	sortedFallbacks := SortZonesByPriority(fallbackValves)

	// Calculate how many valves we need to open
	shortage := minValvesOpen - openCount

	// Return the required number of fallback valves to open (highest priority first)
	result := []string{}
	count := 0
	for _, z := range sortedFallbacks {
		if count >= shortage {
			break
		}
		result = append(result, z.ID)
		count++
	}

	return result
}

// PlanValveOperations plans valve operations with open-first-then-close sequencing
// Returns two slices: operations to open valves, and operations to close valves
func PlanValveOperations(zones []models.ZoneState, actuationDelay int) ([]ValveOperation, []ValveOperation) {
	openOps := []ValveOperation{}
	closeOps := []ValveOperation{}

	for _, zone := range zones {
		// Skip if valve is locked
		if IsValveLocked(zone) {
			continue
		}

		// Skip if valve cannot be actuated yet (chattering prevention)
		if !CanActuateValve(zone, actuationDelay) {
			continue
		}

		// Determine if valve should be opened
		if ShouldOpenValve(zone) {
			openOps = append(openOps, ValveOperation{
				ZoneID:    zone.ID,
				Operation: "open",
				Priority:  zone.Priority,
			})
		}

		// Determine if valve should be closed
		if ShouldCloseValve(zone) {
			closeOps = append(closeOps, ValveOperation{
				ZoneID:    zone.ID,
				Operation: "close",
				Priority:  zone.Priority,
			})
		}
	}

	// Sort operations by priority (higher priority first)
	sortOps := func(ops []ValveOperation) {
		slices.SortFunc(ops, func(a, b ValveOperation) int {
			// Higher priority comes first
			if a.Priority != b.Priority {
				return b.Priority - a.Priority
			}
			// If priorities are equal, sort by zone ID for consistency
			if a.ZoneID < b.ZoneID {
				return -1
			} else if a.ZoneID > b.ZoneID {
				return 1
			}
			return 0
		})
	}

	sortOps(openOps)
	sortOps(closeOps)

	return openOps, closeOps
}

// ExecuteValveOperations executes valve operations in the correct sequence:
// 1. Open valves first (to ensure flow)
// 2. Close valves second (to prevent flow restriction)
// This ensures there's always adequate flow in the system
func ExecuteValveOperations(openOps []ValveOperation, closeOps []ValveOperation, zones []models.ZoneState, minValvesOpen int) []ValveOperation {
	// Create a map for quick zone lookup
	zoneMap := make(map[string]*models.ZoneState)
	for i := range zones {
		zoneMap[zones[i].ID] = &zones[i]
	}

	executedOps := []ValveOperation{}

	// First, execute all open operations
	for _, op := range openOps {
		if zone, exists := zoneMap[op.ZoneID]; exists {
			// Mark valve as open (in-memory simulation)
			zone.ValveState = "open"
			now := time.Now()
			zone.LastActuated = &now
			executedOps = append(executedOps, op)
		}
	}

	// Second, execute close operations, but respect minimum valves requirement
	currentOpenCount := 0
	for _, z := range zones {
		if z.Enabled && z.ValveState == "open" {
			currentOpenCount++
		}
	}

	for _, op := range closeOps {
		// Check if closing this valve would violate minimum requirement
		if currentOpenCount <= minValvesOpen {
			// Cannot close this valve - would violate minimum requirement
			continue
		}

		if zone, exists := zoneMap[op.ZoneID]; exists {
			// Only close if it won't violate minimum requirement
			zone.ValveState = "closed"
			now := time.Now()
			zone.LastActuated = &now
			executedOps = append(executedOps, op)
			currentOpenCount--
		}
	}

	return executedOps
}
