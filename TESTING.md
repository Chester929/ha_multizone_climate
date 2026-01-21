# Test Documentation

This document provides a comprehensive overview of all tests in the ha_multizone_climate project.

## Test Structure

The project has three layers of testing:

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test component interactions and system integration
3. **End-to-End Tests** - Test the complete system with all services running

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

### HomeAssistant Integration Tests (`logic/internal/homeassistant/integration_test.go`)

#### 8 test suites covering HA <-> Addon integration
- **Integration Creation**: Valid/invalid configurations
- **Main Temperature Control**: 0.5°C precision enforcement
- **Valve State Control**: Open/close operations
- **Temperature Sensor Reading**: Get current temperature
- **Zone Temperature Control**: 0.1°C precision enforcement
- **Zone Enable/Disable**: Turn zones on/off
- **HVAC Action Reporting**: 
  - Valve closed → "idle" state
  - Valve open → "heating" or "cooling" state

**Key Requirements Verified:**
- ✅ Addon provides climate entity per zone
- ✅ Zone target temp can be changed by 0.1°C
- ✅ Main climate can be changed by 0.5°C
- ✅ Zone can be turned on/off
- ✅ Current temp read from sensor
- ✅ HVAC state is "idle" when valve closed

### Worker/Processor Tests (`logic/internal/worker/processor_test.go`)

#### 6 test suites covering workflow integration
- **Processor Creation**: With various dependency configurations
- **LastActuated Timestamp**: Proper time tracking
- **Temperature Precision in Workflow**:
  - Zone temperatures: 0.1°C increments verified
  - Main climate: 0.5°C increments verified
- **Zone State Management**:
  - Enable/disable functionality
  - Valve state transitions (open/closed)
  - HVAC action based on valve state
- **Main Climate Control**:
  - Read current temperature
  - Set target temperature
  - Verify 0.5°C precision
  - Main climate drives zones coordination

**Key Requirements Verified:**
- ✅ Full workflow respects temperature precision
- ✅ Main climate already exists in HA (read current, write target)
- ✅ Zones are controlled individually
- ✅ Valve state determines HVAC action

### Other Unit Tests

- **API Handler Tests** (`logic/internal/api/handlers_test.go`)
- **Statistics Tests** (`logic/internal/statistics/*_test.go`)

## Integration Tests (`tests/integration/`)

### Bash Integration Tests (run-tests.sh)

**Purpose**: Test service orchestration and API integration

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

#### MQTT Integration Tests
12. MQTT broker connectivity (via mqtt-tests.js)
13. Topic subscription
14. Message publishing
15. HA discovery messages

#### End-to-End Tests
16. Full zone lifecycle (create, read, update, delete)
17. Cross-service data flow

**Note**: These tests are **useful** and should be kept. They verify that:
- All services start correctly
- Services can communicate with each other
- Data persists across service boundaries
- The system works as an integrated whole

## Test Coverage Summary

### Core Algorithm Logic
- **18 test suites** with 50+ test cases
- Complete coverage of temperature calculation
- Complete coverage of valve management
- Edge cases and boundary conditions tested
- Precision requirements verified (0.1°C and 0.5°C)

### HA Integration
- **8 test suites** covering all HA interactions
- Climate entity management
- Sensor reading
- Valve control
- HVAC state reporting
- Temperature precision verified

### Workflow Integration
- **6 test suites** covering processor logic
- Full workflow tested
- State management verified
- Precision requirements validated

### System Integration
- **17 integration tests** covering service orchestration
- Health checks
- API functionality
- Data persistence
- MQTT communication

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
go test ./internal/homeassistant -v
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
| Main climate drives zones | ✅ | worker/processor_test.go |
| Zone enable/disable | ✅ | homeassistant/integration_test.go, worker/processor_test.go |
| Valve closed = idle HVAC | ✅ | homeassistant/integration_test.go, worker/processor_test.go |
| Valve open = heating/cooling | ✅ | homeassistant/integration_test.go |
| Read temp from sensor | ✅ | homeassistant/integration_test.go |
| Climate entity per zone | ✅ | homeassistant/integration_test.go |
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
