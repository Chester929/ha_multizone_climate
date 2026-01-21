# Test Documentation

This document provides a comprehensive overview of all tests in the ha_multizone_climate project.

## Test Structure

The project has three layers of testing:

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test component interactions and system integration (addon services)
3. **End-to-End Tests** - Test the complete system with all services running

## Addon-Only Architecture

This project is a **Home Assistant Addon** with a containerized architecture. It does NOT:
- Make direct API calls to Home Assistant
- Use MQTT for communication
- Auto-discover or auto-create entities

Instead, the addon:
- Stores entity IDs that users manually configure
- Calculates intended states (valve open/close, temperature targets)
- Can be used by HA automations to actually control entities
- Provides a UI through HA Ingress for configuration and monitoring

## Unit Tests

### Algorithm Tests (`logic/internal/algorithm/*_test.go`)

#### Original Tests (temperature_test.go, valve_test.go)
- **12 test suites** covering core algorithm functionality
- Temperature calculation (average mode, overheated zones, thresholds)
- Zone satisfaction determination
- Minimum valves enforcement
- Valve actuation timing (chattering prevention)
- Valve locking/unlocking
- Zone priority sorting
- Valve operation planning and execution

#### Extended Algorithm Tests (temperature_extended_test.go)
- **6 additional test suites** with 24+ test cases
- **Main Climate Precision Tests**: Verifies 0.5°C rounding (per requirements)
  - Tests: 21.25 → 21.5, 20.75 → 21.0, 20.24 → 20.0
- **Slider Mode Tests**: Various slider positions (0.0, 0.25, 0.5, 1.0)
- **Boundary Condition Tests**: Min/max temperature clamping
- **Disabled Zones Tests**: Proper handling of enabled/disabled zones
- **Satisfaction Edge Cases**: Precise threshold testing with epsilon
- **Valve Action Tests**: Open/close decision logic

**Key Requirements Verified:**
- ✅ Main climate uses 0.5°C precision
- ✅ Zones can use 0.1°C precision
- ✅ Proper min/max clamping
- ✅ Disabled zones are excluded
- ✅ Valve safety logic works correctly

### Worker/Processor Tests (`logic/internal/worker/processor_test.go`)

#### Test suites covering addon workflow
- **Processor Creation**: With various dependency configurations
- **LastActuated Timestamp**: Proper time tracking
- **Temperature Precision in Workflow**:
  - Zone temperatures: 0.1°C increments verified
  - Main climate: 0.5°C increments verified
- **Zone State Management**:
  - Enable/disable functionality
  - Valve state transitions (open/closed)
  - Zone state stored in addon (not directly controlled)
- **Main Climate Control**:
  - Read current temperature
  - Set target temperature
  - Verify 0.5°C precision
  - Entity ID storage in addon

**Key Requirements Verified:**
- ✅ Full workflow respects temperature precision
- ✅ Main climate entity ID stored (addon doesn't control it directly)
- ✅ Zones valve states tracked (addon calculates intended states)
- ✅ Addon stores configuration but doesn't make HA API calls

### Other Unit Tests

- **API Handler Tests** (`logic/internal/api/handlers_test.go`)
- **Statistics Tests** (`logic/internal/statistics/*_test.go`)

## Integration Tests (`tests/integration/`)

### Bash Integration Tests (run-tests.sh)

**Purpose**: Test addon service orchestration and API integration

#### Service Health Checks
1. Logic service health endpoint
2. Logic service Redis connection
3. Frontend service availability
4. Frontend SPA routing
5. Redis connectivity

#### API Endpoint Tests
6. List zones endpoint
7. Metrics endpoint
8. Create and retrieve zone
9. Update zone via API

#### Redis Integration Tests
10. Data persistence (SET/GET)
11. Hash operations (HSET/HGET)

#### End-to-End Tests
12. Full zone lifecycle (create, read, update, delete)
13. Cross-service data flow

**Note**: These tests verify that:
- All addon services start correctly
- Services can communicate with each other
- Data persists across service boundaries
- The addon works as an integrated whole
- NO MQTT tests (MQTT was removed in addon-only architecture)
- NO direct HA API tests (addon uses manual entity ID configuration)

## Test Coverage Summary

### Core Algorithm Logic
- **18 test suites** with 50+ test cases
- Complete coverage of temperature calculation
- Complete coverage of valve management
- Edge cases and boundary conditions tested
- Precision requirements verified (0.1°C and 0.5°C)

### Addon Workflow
- **Test suites** covering processor logic
- Full workflow tested
- State management verified
- Precision requirements validated
- Addon-only architecture verified (no direct HA API calls)

### Addon Service Integration
- **13 integration tests** covering service orchestration
- Health checks
- API functionality
- Data persistence
- **NO MQTT tests** (MQTT removed in addon-only architecture)

## Running Tests

### Run All Unit Tests
```bash
cd logic
go test ./...
```

### Run Specific Package Tests
```bash
cd logic
go test ./internal/algorithm -v
go test ./internal/worker -v
```

### Run Integration Tests
```bash
make test-integration
# or
cd tests/integration
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

### Run Tests with Coverage
```bash
cd logic
go test ./... -cover
```

## Key Requirements Verification

| Requirement | Verified | Test Location |
|------------|----------|---------------|
| Zone temp precision 0.1°C | ✅ | algorithm/temperature_extended_test.go, worker/processor_test.go |
| Main climate precision 0.5°C | ✅ | algorithm/temperature_extended_test.go, worker/processor_test.go |
| Addon stores entity IDs | ✅ | worker/processor_test.go |
| Addon calculates intended states | ✅ | worker/processor_test.go |
| No direct HA API calls | ✅ | worker/processor.go (all HA integration removed) |
| Manual entity configuration | ✅ | Addon-only architecture |
| Main logic scenarios | ✅ | algorithm/*_test.go (50+ test cases) |

## Adding New Tests

### For New Algorithm Features
Add tests to `logic/internal/algorithm/` following the existing pattern:
```go
func TestNewFeature(t *testing.T) {
    tests := []struct {
        name     string
        input    Type
        expected Type
    }{
        // test cases
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // test logic
        })
    }
}
```

### For New HA Integration Features
Add tests to `logic/internal/homeassistant/integration_test.go`

### For New Workflow Features
Add tests to `logic/internal/worker/processor_test.go`

### For New Integration Tests
Add tests to `tests/integration/run-tests.sh` following the existing pattern

## Test Maintenance

- Run tests before committing changes
- Add tests for new features
- Update tests when requirements change
- Keep test data isolated and clean
- Use descriptive test names
- Document complex test scenarios
