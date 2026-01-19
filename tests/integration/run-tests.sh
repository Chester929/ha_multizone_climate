#!/bin/bash

set -e

echo "======================================"
echo "Multizone Climate Integration Tests"
echo "======================================"
echo ""

# Configuration
LOGIC_URL="${LOGIC_URL:-http://logic-test:8080}"
FRONTEND_URL="${FRONTEND_URL:-http://frontend-test:8099}"
REDIS_HOST="${REDIS_HOST:-redis-test}"
REDIS_PORT="${REDIS_PORT:-6379}"
MQTT_BROKER="${MQTT_BROKER:-mqtt-broker-test}"
MQTT_PORT="${MQTT_PORT:-1883}"

RESULTS_DIR="/results"
mkdir -p "$RESULTS_DIR"

FAILED=0
PASSED=0

# Helper functions
pass_test() {
    echo "✓ PASS: $1"
    ((PASSED++))
}

fail_test() {
    echo "✗ FAIL: $1"
    ((FAILED++))
}

# Wait for services to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    echo "Waiting for $name to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo "$name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo "ERROR: $name failed to become ready"
    return 1
}

echo "===== Service Health Checks ====="
echo ""

# Test 1: Logic Service Health
echo "Test 1: Logic Service Health Check"
if wait_for_service "$LOGIC_URL/health" "Logic Service"; then
    response=$(curl -s "$LOGIC_URL/health")
    if echo "$response" | jq -e '.status == "healthy"' > /dev/null; then
        pass_test "Logic service is healthy"
    else
        fail_test "Logic service health check returned unexpected response"
    fi
else
    fail_test "Logic service is not responding"
fi

# Test 2: Logic Service Status
echo ""
echo "Test 2: Logic Service Status"
response=$(curl -s "$LOGIC_URL/status")
if echo "$response" | jq -e '.redis == "connected"' > /dev/null; then
    pass_test "Logic service connected to Redis"
else
    fail_test "Logic service not connected to Redis"
fi

# Test 3: Frontend Service Health
echo ""
echo "Test 3: Frontend Service Health Check"
if curl -sf "$FRONTEND_URL/health" > /dev/null 2>&1; then
    pass_test "Frontend service is responding"
else
    fail_test "Frontend service is not responding"
fi

# Test 3a: Frontend Serves index.html
echo ""
echo "Test 3a: Frontend Serves index.html"
response=$(curl -s "$FRONTEND_URL/" -w "\n%{http_code}")
http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | head -n -1)

if [ "$http_code" = "200" ]; then
    if echo "$body" | grep -q "Multizone Climate Control"; then
        pass_test "Frontend serves index.html successfully"
    else
        fail_test "Frontend returned 200 but index.html content is missing"
    fi
else
    fail_test "Frontend failed to serve index.html (HTTP $http_code)"
fi

# Test 3b: Frontend Serves Static Assets
echo ""
echo "Test 3b: Frontend Static Asset Path Test"
# Try to access a non-existent route (should still serve index.html for SPA routing)
response=$(curl -s "$FRONTEND_URL/some-route" -w "\n%{http_code}")
http_code=$(echo "$response" | tail -n 1)

if [ "$http_code" = "200" ]; then
    pass_test "Frontend catch-all route serves index.html"
else
    fail_test "Frontend catch-all route failed (HTTP $http_code)"
fi

# Test 4: Redis Connection
echo ""
echo "Test 4: Redis Connection"
if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping | grep -q "PONG"; then
    pass_test "Redis is responding to PING"
else
    fail_test "Redis is not responding"
fi

echo ""
echo "===== API Endpoint Tests ====="
echo ""

# Test 5: List Zones Endpoint
echo "Test 5: List Zones Endpoint"
response=$(curl -s "$LOGIC_URL/api/zones")
if [ $? -eq 0 ]; then
    pass_test "Zones endpoint is accessible"
else
    fail_test "Zones endpoint is not accessible"
fi

# Test 6: Metrics Endpoint
echo ""
echo "Test 6: Metrics Endpoint"
response=$(curl -s "$LOGIC_URL/metrics")
if echo "$response" | jq -e 'has("zones_count")' > /dev/null 2>&1; then
    pass_test "Metrics endpoint returns zones_count"
else
    fail_test "Metrics endpoint missing zones_count"
fi

# Test 7: Create Test Zone
echo ""
echo "Test 7: Create and Retrieve Zone"
zone_id="test_zone_$$"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HSET "multizone:zone:${zone_id}" \
    id "$zone_id" \
    name "Test Zone" \
    target_temperature "21.5" \
    current_temperature "20.0" \
    enabled "true" > /dev/null

response=$(curl -s "$LOGIC_URL/api/zones/${zone_id}")
if echo "$response" | jq -e '.id' > /dev/null 2>&1; then
    pass_test "Zone created and retrieved successfully"
else
    fail_test "Failed to create/retrieve zone"
fi

# Test 8: Update Zone
echo ""
echo "Test 8: Update Zone"
update_response=$(curl -s -X PUT "$LOGIC_URL/api/zones/${zone_id}" \
    -H "Content-Type: application/json" \
    -d '{"target_temperature": "22.0"}')

if echo "$update_response" | jq -e '.status == "updated"' > /dev/null 2>&1; then
    # Verify the update
    temp=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HGET "multizone:zone:${zone_id}" target_temperature)
    if [ "$temp" = "22.0" ]; then
        pass_test "Zone updated successfully"
    else
        fail_test "Zone update did not persist to Redis"
    fi
else
    fail_test "Failed to update zone"
fi

echo ""
echo "===== Redis Integration Tests ====="
echo ""

# Test 9: Redis Data Persistence
echo "Test 9: Redis Data Persistence"
test_key="multizone:test:$$"
test_value="integration_test_value"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$test_key" "$test_value" > /dev/null
retrieved=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET "$test_key")

if [ "$retrieved" = "$test_value" ]; then
    pass_test "Redis data persistence works"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "$test_key" > /dev/null
else
    fail_test "Redis data persistence failed"
fi

# Test 10: Redis Hash Operations
echo ""
echo "Test 10: Redis Hash Operations"
hash_key="multizone:test_hash:$$"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HSET "$hash_key" field1 value1 field2 value2 > /dev/null
field1_val=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HGET "$hash_key" field1)

if [ "$field1_val" = "value1" ]; then
    pass_test "Redis hash operations work"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "$hash_key" > /dev/null
else
    fail_test "Redis hash operations failed"
fi

echo ""
echo "===== MQTT Integration Tests ====="
echo ""

# Run MQTT tests using Node.js
if [ -f "/tests/mqtt-tests.js" ]; then
    echo "Running MQTT integration tests..."
    cd /tests
    node mqtt-tests.js
    mqtt_result=$?
    if [ $mqtt_result -eq 0 ]; then
        pass_test "MQTT integration tests passed"
    else
        fail_test "MQTT integration tests failed"
    fi
else
    echo "⚠ WARNING: MQTT test script not found, skipping MQTT tests"
fi

echo ""
echo "===== End-to-End Tests ====="
echo ""

# Test 11: Full Zone Lifecycle
echo "Test 11: Full Zone Lifecycle Test"
lifecycle_zone="lifecycle_test_$$"

# Create zone
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HSET "multizone:zone:${lifecycle_zone}" \
    id "$lifecycle_zone" \
    name "Lifecycle Test Zone" \
    target_temperature "21.0" \
    current_temperature "19.5" \
    enabled "true" > /dev/null

# Retrieve via API
api_response=$(curl -s "$LOGIC_URL/api/zones/${lifecycle_zone}")
if echo "$api_response" | jq -e '.id' > /dev/null 2>&1; then
    # Update via API
    curl -s -X PUT "$LOGIC_URL/api/zones/${lifecycle_zone}" \
        -H "Content-Type: application/json" \
        -d '{"current_temperature": "20.0"}' > /dev/null
    
    # Verify update
    new_temp=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HGET "multizone:zone:${lifecycle_zone}" current_temperature)
    if [ "$new_temp" = "20.0" ]; then
        pass_test "Full zone lifecycle test completed"
    else
        fail_test "Zone lifecycle update verification failed"
    fi
    
    # Cleanup
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "multizone:zone:${lifecycle_zone}" > /dev/null
else
    fail_test "Zone lifecycle creation failed"
fi

# Cleanup test zone
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "multizone:zone:${zone_id}" > /dev/null

echo ""
echo "======================================"
echo "Test Results Summary"
echo "======================================"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Total:  $((PASSED + FAILED))"
echo ""

# Write results to file
cat > "$RESULTS_DIR/results.json" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total": $((PASSED + FAILED)),
  "passed": $PASSED,
  "failed": $FAILED,
  "success": $([ $FAILED -eq 0 ] && echo "true" || echo "false")
}
EOF

if [ $FAILED -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi
