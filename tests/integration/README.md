# Integration Tests

This directory contains comprehensive integration tests for the Multizone Climate system.

## Purpose

These integration tests verify that all system components work together correctly:
- **Service orchestration** - All containers start and communicate
- **API functionality** - REST endpoints work end-to-end
- **Data persistence** - Redis stores and retrieves data correctly
- **Full workflows** - Complete user scenarios function properly

**Note**: These tests complement the unit tests by verifying integration between components. While unit tests verify individual components work correctly (algorithm logic, HA integration functions), integration tests verify the complete system works together.

## Relationship to Unit Tests

- **Unit Tests** (`logic/internal/*/test.go`) - Test individual components:
  - Algorithm logic (temperature calculation, valve management)
  - HA integration functions (climate entity control, sensor reading)
  - Worker/processor logic (workflow coordination)
  
- **Integration Tests** (this directory) - Test component interactions:
  - Service health and connectivity
  - API request/response flows
  - Database persistence
  - Inter-service communication

Both are necessary for comprehensive test coverage.

## Overview

The integration test suite validates the entire system working together, including:

- **End-to-End Testing**: Complete system functionality from API to Redis
- **Docker Compose Integration**: Service orchestration and dependencies
- **API Endpoint Testing**: REST API functionality and data persistence
- **Redis Integration**: Data storage and retrieval

## Architecture

The test suite uses Docker Compose to spin up isolated instances of all services:

- `logic-test`: Logic/API service
- `redis-test`: Redis database
- `test-runner`: Test execution container

## Prerequisites

- Docker and Docker Compose installed
- Make (optional, for using Makefile commands)
- Sufficient system resources (containers will run in parallel)

## Running Tests

### Using Make (Recommended)

```bash
# Run all integration tests
make test-integration

# Run tests with verbose output
make test-integration-verbose

# Clean up test containers and volumes
make test-integration-clean
```

### Using Docker Compose Directly

```bash
# Navigate to the integration test directory
cd tests/integration

# Run the test suite
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Clean up after tests
docker-compose -f docker-compose.test.yml down -v
```

### Running Individual Test Scripts

```bash
# Run the integration tests
docker-compose -f docker-compose.test.yml run --rm test-runner ./run-tests.sh
```

## Test Coverage

### Service Health Checks

- Logic service health endpoint
- Logic service status and Redis connectivity
- Redis connectivity and responsiveness

### API Endpoint Tests

- `GET /health` - Health check endpoint
- `GET /status` - Service status
- `GET /metrics` - System metrics
- `GET /api/zones` - List all zones
- `GET /api/zones/{id}` - Get specific zone
- `PUT /api/zones/{id}` - Update zone

### Redis Integration Tests

- Data persistence (SET/GET operations)
- Hash operations (HSET/HGET)
- Key pattern matching
- Zone data storage and retrieval

### End-to-End Tests

- Full zone lifecycle (create, read, update, delete)
- API to Redis integration
- Cross-service communication
- Data consistency validation

## Test Results

Test results are stored in the `results/` directory:

- `results/results.json` - JSON summary of test execution

Example results format:

```json
{
  "timestamp": "2024-01-16T19:00:00Z",
  "total": 10,
  "passed": 10,
  "failed": 0,
  "success": true
}
```

## Test Configuration

### Environment Variables

The following environment variables can be configured in `docker-compose.test.yml`:

- `REDIS_HOST` - Redis hostname (default: redis-test)
- `REDIS_PORT` - Redis port (default: 6379)
- `LOGIC_URL` - Logic service URL (default: http://logic-test:8080)

### Network Configuration

All test services run on an isolated Docker network (`multizone-test-network`) to avoid conflicts with production services.

### Port Mapping

Test services use non-conflicting ports:

- Logic: 18080 (external) → 8080 (internal)
- Redis: 16379 (external) → 6379 (internal)

## Adding New Tests

### Adding Bash Tests

Edit `run-tests.sh` and add your test following this pattern:

```bash
echo ""
echo "Test N: Your Test Name"
# Your test logic here
if [ test_condition ]; then
    pass_test "Your Test Name"
else
    fail_test "Your Test Name"
fi
```

## Troubleshooting

### Tests Hang or Timeout

- Check if all services are healthy: `docker-compose -f docker-compose.test.yml ps`
- View service logs: `docker-compose -f docker-compose.test.yml logs`
- Increase health check timeouts in `docker-compose.test.yml`

### Redis Connection Issues

- Check Redis is healthy: `docker-compose -f docker-compose.test.yml exec redis-test redis-cli ping`
- Verify Redis logs: `docker-compose -f docker-compose.test.yml logs redis-test`
- Ensure port 16379 is not in use

### API Tests Fail

- Verify logic service is healthy: `curl http://localhost:18080/health`
- Check logic service logs: `docker-compose -f docker-compose.test.yml logs logic-test`
- Ensure the service had enough time to start (check `start_period` in health checks)

## CI/CD Integration

These tests are designed to run in CI/CD pipelines. Example GitHub Actions workflow:

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Integration Tests
        run: |
          cd tests/integration
          docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
          
      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: tests/integration/results/
```

## Performance Considerations

- Test suite typically completes in 2-5 minutes
- Uses ~2GB RAM and ~1GB disk space
- Services start in parallel where possible
- Health checks ensure services are ready before tests run

## Maintenance

- Review and update tests when adding new features
- Keep test data isolated and clean up after each test
- Monitor test execution time and optimize slow tests
- Update documentation when test coverage changes

## Contributing

When contributing new tests:

1. Ensure tests are idempotent (can run multiple times safely)
2. Clean up test data after each test
3. Add appropriate error handling
4. Update this README with new test descriptions
5. Follow existing test patterns and naming conventions
