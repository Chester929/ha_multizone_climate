package algorithm

import (
	"testing"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
)

func TestCanActuateValve(t *testing.T) {
	now := time.Now()
	past := now.Add(-10 * time.Second)
	recent := now.Add(-2 * time.Second)

	tests := []struct {
		name           string
		zone           models.ZoneState
		actuationDelay int
		expectedCanAct bool
	}{
		{
			name: "Never actuated before",
			zone: models.ZoneState{
				ID:           "zone1",
				LastActuated: nil,
			},
			actuationDelay: 5,
			expectedCanAct: true,
		},
		{
			name: "Enough time has passed",
			zone: models.ZoneState{
				ID:           "zone1",
				LastActuated: &past,
			},
			actuationDelay: 5,
			expectedCanAct: true,
		},
		{
			name: "Not enough time has passed",
			zone: models.ZoneState{
				ID:           "zone1",
				LastActuated: &recent,
			},
			actuationDelay: 5,
			expectedCanAct: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			canAct := CanActuateValve(tt.zone, tt.actuationDelay)
			if canAct != tt.expectedCanAct {
				t.Errorf("CanActuateValve() = %v, want %v", canAct, tt.expectedCanAct)
			}
		})
	}
}

func TestIsValveLocked(t *testing.T) {
	now := time.Now()
	future := now.Add(10 * time.Second)
	past := now.Add(-10 * time.Second)

	tests := []struct {
		name           string
		zone           models.ZoneState
		expectedLocked bool
	}{
		{
			name: "No lock",
			zone: models.ZoneState{
				ID:                  "zone1",
				ValveLockExpiration: nil,
			},
			expectedLocked: false,
		},
		{
			name: "Lock not expired",
			zone: models.ZoneState{
				ID:                  "zone1",
				ValveLockExpiration: &future,
			},
			expectedLocked: true,
		},
		{
			name: "Lock expired",
			zone: models.ZoneState{
				ID:                  "zone1",
				ValveLockExpiration: &past,
			},
			expectedLocked: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			locked := IsValveLocked(tt.zone)
			if locked != tt.expectedLocked {
				t.Errorf("IsValveLocked() = %v, want %v", locked, tt.expectedLocked)
			}
		})
	}
}

func TestLockValve(t *testing.T) {
	zone := models.ZoneState{ID: "zone1"}
	lockDuration := 10 * time.Second

	LockValve(&zone, lockDuration)

	if zone.ValveLockExpiration == nil {
		t.Error("Expected lock to be set")
	}

	if !IsValveLocked(zone) {
		t.Error("Valve should be locked")
	}

	// Check that lock expires approximately at the right time
	expectedExpiration := time.Now().Add(lockDuration)
	if zone.ValveLockExpiration.Before(expectedExpiration.Add(-1*time.Second)) ||
		zone.ValveLockExpiration.After(expectedExpiration.Add(1*time.Second)) {
		t.Error("Lock expiration time is not as expected")
	}
}

func TestUnlockValve(t *testing.T) {
	future := time.Now().Add(10 * time.Second)
	zone := models.ZoneState{
		ID:                  "zone1",
		ValveLockExpiration: &future,
	}

	UnlockValve(&zone)

	if zone.ValveLockExpiration != nil {
		t.Error("Expected lock to be removed")
	}

	if IsValveLocked(zone) {
		t.Error("Valve should not be locked")
	}
}

func TestSortZonesByPriority(t *testing.T) {
	zones := []models.ZoneState{
		{ID: "zone1", Priority: 2},
		{ID: "zone2", Priority: 5},
		{ID: "zone3", Priority: 1},
		{ID: "zone4", Priority: 5},
		{ID: "zone5", Priority: 3},
	}

	sorted := SortZonesByPriority(zones)

	// Check order: zone2 (5), zone4 (5), zone5 (3), zone1 (2), zone3 (1)
	if sorted[0].Priority != 5 || sorted[1].Priority != 5 {
		t.Error("Highest priority zones should be first")
	}

	if sorted[4].Priority != 1 {
		t.Error("Lowest priority zone should be last")
	}

	// Verify zones with same priority are sorted by ID
	if sorted[0].Priority == 5 && sorted[1].Priority == 5 {
		if sorted[0].ID > sorted[1].ID {
			t.Error("Zones with same priority should be sorted by ID")
		}
	}
}

func TestCheckMinimumValvesByPriority(t *testing.T) {
	tests := []struct {
		name            string
		zones           []models.ZoneState
		minValvesOpen   int
		expectedCount   int
		highestPriority bool
	}{
		{
			name: "Sufficient valves open",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "open", Priority: 1},
				{ID: "zone2", Enabled: true, ValveState: "open", Priority: 2},
			},
			minValvesOpen:   1,
			expectedCount:   0,
			highestPriority: false,
		},
		{
			name: "Need to open fallback valve - select highest priority",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 1},
				{ID: "zone2", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 5},
				{ID: "zone3", Enabled: true, ValveState: "closed", IsFallbackValve: false, Priority: 3},
			},
			minValvesOpen:   1,
			expectedCount:   1,
			highestPriority: true,
		},
		{
			name: "Need to open multiple fallback valves",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 1},
				{ID: "zone2", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 2},
				{ID: "zone3", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 3},
			},
			minValvesOpen:   2,
			expectedCount:   2,
			highestPriority: true,
		},
		{
			name: "Skip already-open fallback valves",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "open", IsFallbackValve: true, Priority: 5},
				{ID: "zone2", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 3},
				{ID: "zone3", Enabled: true, ValveState: "closed", IsFallbackValve: true, Priority: 1},
			},
			minValvesOpen:   2,
			expectedCount:   1,
			highestPriority: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			valves := CheckMinimumValvesByPriority(tt.zones, tt.minValvesOpen)
			if len(valves) != tt.expectedCount {
				t.Errorf("Expected %d valves to open, got %d", tt.expectedCount, len(valves))
			}

			// If we expect highest priority, verify it
			if tt.highestPriority && len(valves) > 0 {
				// Find the zone with the selected ID
				for _, z := range tt.zones {
					if z.ID == valves[0] {
						// This should be the highest priority among CLOSED fallback valves
						for _, other := range tt.zones {
							// Only compare with other closed fallback valves
							if other.IsFallbackValve && other.ID != z.ID && other.ValveState != "open" {
								if other.Priority > z.Priority {
									t.Errorf("Selected zone has priority %d, but zone %s has higher priority %d",
										z.Priority, other.ID, other.Priority)
								}
							}
						}
						break
					}
				}
			}
		})
	}
}

func TestPlanValveOperations(t *testing.T) {
	now := time.Now()
	past := now.Add(-10 * time.Second)
	future := now.Add(10 * time.Second)

	tests := []struct {
		name               string
		zones              []models.ZoneState
		actuationDelay     int
		expectedOpenCount  int
		expectedCloseCount int
	}{
		{
			name: "Plan open and close operations",
			zones: []models.ZoneState{
				{
					ID:           "zone1",
					Satisfaction: "underheated",
					ValveState:   "closed",
					Priority:     5,
				},
				{
					ID:           "zone2",
					Satisfaction: "overheated",
					ValveState:   "open",
					Priority:     3,
				},
			},
			actuationDelay:     5,
			expectedOpenCount:  1,
			expectedCloseCount: 1,
		},
		{
			name: "Skip locked valves",
			zones: []models.ZoneState{
				{
					ID:                  "zone1",
					Satisfaction:        "underheated",
					ValveState:          "closed",
					ValveLockExpiration: &future,
				},
			},
			actuationDelay:     5,
			expectedOpenCount:  0,
			expectedCloseCount: 0,
		},
		{
			name: "Skip recently actuated valves (chattering prevention)",
			zones: []models.ZoneState{
				{
					ID:           "zone1",
					Satisfaction: "underheated",
					ValveState:   "closed",
					LastActuated: &now,
				},
			},
			actuationDelay:     5,
			expectedOpenCount:  0,
			expectedCloseCount: 0,
		},
		{
			name: "Allow actuation of valves actuated long ago",
			zones: []models.ZoneState{
				{
					ID:           "zone1",
					Satisfaction: "underheated",
					ValveState:   "closed",
					LastActuated: &past,
					Priority:     1,
				},
			},
			actuationDelay:     5,
			expectedOpenCount:  1,
			expectedCloseCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			openOps, closeOps := PlanValveOperations(tt.zones, tt.actuationDelay)

			if len(openOps) != tt.expectedOpenCount {
				t.Errorf("Expected %d open operations, got %d", tt.expectedOpenCount, len(openOps))
			}

			if len(closeOps) != tt.expectedCloseCount {
				t.Errorf("Expected %d close operations, got %d", tt.expectedCloseCount, len(closeOps))
			}

			// Verify operations are sorted by priority
			for i := 1; i < len(openOps); i++ {
				if openOps[i].Priority > openOps[i-1].Priority {
					t.Error("Open operations are not sorted by priority (descending)")
				}
			}

			for i := 1; i < len(closeOps); i++ {
				if closeOps[i].Priority > closeOps[i-1].Priority {
					t.Error("Close operations are not sorted by priority (descending)")
				}
			}
		})
	}
}

func TestExecuteValveOperations(t *testing.T) {
	tests := []struct {
		name          string
		zones         []models.ZoneState
		openOps       []ValveOperation
		closeOps      []ValveOperation
		minValvesOpen int
		expectedExec  int
		expectedOpen  int
	}{
		{
			name: "Execute open then close",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed"},
				{ID: "zone2", Enabled: true, ValveState: "open"},
			},
			openOps: []ValveOperation{
				{ZoneID: "zone1", Operation: "open", Priority: 5},
			},
			closeOps: []ValveOperation{
				{ZoneID: "zone2", Operation: "close", Priority: 3},
			},
			minValvesOpen: 1,
			expectedExec:  2,
			expectedOpen:  1,
		},
		{
			name: "Respect minimum valves requirement",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "open"},
			},
			openOps: []ValveOperation{},
			closeOps: []ValveOperation{
				{ZoneID: "zone1", Operation: "close", Priority: 1},
			},
			minValvesOpen: 1,
			expectedExec:  0, // Close should not execute
			expectedOpen:  1, // Valve should remain open
		},
		{
			name: "Open first ensures flow before closing",
			zones: []models.ZoneState{
				{ID: "zone1", Enabled: true, ValveState: "closed"},
				{ID: "zone2", Enabled: true, ValveState: "open"},
				{ID: "zone3", Enabled: true, ValveState: "open"},
			},
			openOps: []ValveOperation{
				{ZoneID: "zone1", Operation: "open", Priority: 5},
			},
			closeOps: []ValveOperation{
				{ZoneID: "zone2", Operation: "close", Priority: 3},
			},
			minValvesOpen: 2,
			expectedExec:  2,
			expectedOpen:  2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			executedOps := ExecuteValveOperations(tt.openOps, tt.closeOps, tt.zones, tt.minValvesOpen)

			if len(executedOps) != tt.expectedExec {
				t.Errorf("Expected %d executed operations, got %d", tt.expectedExec, len(executedOps))
			}

			// Count open valves after execution
			openCount := 0
			for _, z := range tt.zones {
				if z.Enabled && z.ValveState == "open" {
					openCount++
				}
			}

			if openCount != tt.expectedOpen {
				t.Errorf("Expected %d open valves after execution, got %d", tt.expectedOpen, openCount)
			}

			// Verify LastActuated is set for executed operations
			for _, op := range executedOps {
				for _, z := range tt.zones {
					if z.ID == op.ZoneID && z.LastActuated == nil {
						t.Errorf("LastActuated should be set for zone %s", z.ID)
					}
				}
			}
		})
	}
}
