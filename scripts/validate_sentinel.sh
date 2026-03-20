
#!/bin/bash

# Sentinel Project Validation Script
# Tests all components across Week 1-4
# Uses direct `docker` commands (not docker compose) for portability

# set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    ((PASS++))
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    ((FAIL++))
}

# ============================================
# WEEK 0: Docker Infrastructure
# ============================================
print_header "WEEK 0: Docker Infrastructure"

print_test "Checking Docker daemon..."
if docker info > /dev/null 2>&1; then
    print_pass "Docker daemon is running"
else
    print_fail "Docker daemon is NOT running"
    exit 1
fi

print_test "Checking docker-compose.yml exists..."
if [ -f "docker-compose.yml" ]; then
    print_pass "docker-compose.yml found"
else
    print_fail "docker-compose.yml NOT found"
fi

print_test "Checking all services are running..."
EXPECTED_SERVICES=("gateway" "kafka" "redis" "influxdb" "postgres" "prometheus" "grafana")
for service in "${EXPECTED_SERVICES[@]}"; do
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "sentinel-$service.*Up"; then
        print_pass "Service sentinel-$service is running"
    else
        print_fail "Service sentinel-$service is NOT running"
    fi
done

# ============================================
# WEEK 1: Go Gateway
# ============================================
print_header "WEEK 1: Go Gateway"

print_test "Testing /health endpoint..."
HEALTH=$(curl -s http://localhost:8080/health)
if echo "$HEALTH" | grep -q "ok"; then
    print_pass "Gateway /health endpoint responding"
    echo "   Response: $HEALTH"
else
    print_fail "Gateway /health endpoint failed"
fi

print_test "Testing JWT authentication (invalid token)..."
INVALID_AUTH=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid.token" http://localhost:8080/api/test)
if [ "$INVALID_AUTH" = "401" ]; then
    print_pass "Invalid JWT correctly rejected (401)"
else
    print_fail "Expected 401, got $INVALID_AUTH"
fi

print_test "Generating valid JWT token..."
if [ -f "scripts/generate_jwt.py" ]; then
    TOKEN=$(python3 scripts/generate_jwt.py --client-id test-validator 2>/dev/null | tr -d '[:space:]')
    if [ -n "$TOKEN" ]; then
        print_pass "JWT token generated successfully"
    else
        print_fail "JWT token generation failed"
    fi
else
    print_fail "scripts/generate_jwt.py not found"
fi

print_test "Testing JWT authentication (valid token)..."
VALID_AUTH=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test 2>/dev/null)
if [ "$VALID_AUTH" = "502" ] || [ "$VALID_AUTH" = "200" ]; then
    print_pass "Valid JWT accepted (got $VALID_AUTH - backend may not exist)"
else
    print_fail "Expected 502/200, got $VALID_AUTH"
fi

print_test "Testing Prometheus metrics endpoint..."
METRICS=$(curl -s http://localhost:8080/metrics | grep "sentinel_gateway_requests_total")
if [ -n "$METRICS" ]; then
    print_pass "Prometheus metrics exposed"
    echo "   Sample: $(echo "$METRICS" | head -1)"
else
    print_fail "Prometheus metrics not found"
fi

print_test "Testing Redis rate limiting..."
REDIS_KEYS=$(docker exec sentinel-redis redis-cli keys "*" 2>/dev/null | wc -l)
if [ "$REDIS_KEYS" -gt 0 ]; then
    print_pass "Redis has $REDIS_KEYS keys (rate limiting active)"
else
    print_fail "Redis is empty (rate limiting may not be working)"
fi

# ============================================
# WEEK 1: Kafka Integration
# ============================================
print_header "WEEK 1: Kafka Integration"

print_test "Checking Kafka topics..."
TOPICS=$(docker exec sentinel-kafka kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null)
if echo "$TOPICS" | grep -q "api.events"; then
    print_pass "Kafka topic 'api.events' exists"
else
    print_fail "Kafka topic 'api.events' does NOT exist"
fi

if echo "$TOPICS" | grep -q "api.features"; then
    print_pass "Kafka topic 'api.features' exists"
else
    print_fail "Kafka topic 'api.features' does NOT exist"
fi

print_test "Generating test traffic to populate Kafka..."
for i in {1..5}; do
    curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test > /dev/null 2>&1
done
sleep 2

print_test "Checking for messages in api.events topic..."
EVENTS_OFFSET=$(docker exec sentinel-kafka kafka-get-offsets --bootstrap-server localhost:9092 --topic api.events 2>/dev/null | awk -F: '{print $3}')
if [ -n "$EVENTS_OFFSET" ] && [ "$EVENTS_OFFSET" -gt 0 ] 2>/dev/null; then
    print_pass "Messages found in api.events topic ($EVENTS_OFFSET messages)"
else
    print_fail "No messages in api.events topic"
fi

# ============================================
# WEEK 2: Kafka Streams / Orchestrator
# ============================================
print_header "WEEK 2: Kafka Streams / Orchestrator"

print_test "Checking if orchestrator service exists..."
if docker ps --format '{{.Names}}' | grep -q "sentinel-orchestrator"; then
    print_pass "Orchestrator service is defined"
    
    print_test "Checking orchestrator service health..."
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "sentinel-orchestrator.*Up"; then
        print_pass "Orchestrator service is running"
        
        print_test "Checking orchestrator logs for Kafka Streams..."
        STREAMS_LOG=$(docker logs sentinel-orchestrator 2>/dev/null | grep -i "kafka\|stream" | head -5)
        if [ -n "$STREAMS_LOG" ]; then
            print_pass "Orchestrator has Kafka Streams activity"
            echo "   $(echo "$STREAMS_LOG" | head -2)"
        else
            print_fail "No Kafka Streams activity in orchestrator logs"
        fi
    else
        print_fail "Orchestrator service is NOT running"
    fi
else
    print_fail "Orchestrator service not found in docker-compose"
fi

print_test "Checking for feature vectors in api.features topic..."
FEATURES_OFFSET=$(docker exec sentinel-kafka kafka-get-offsets --bootstrap-server localhost:9092 --topic api.features 2>/dev/null | awk -F: '{print $3}')
if [ -n "$FEATURES_OFFSET" ] && [ "$FEATURES_OFFSET" -gt 0 ] 2>/dev/null; then
    print_pass "Feature vectors found in api.features topic ($FEATURES_OFFSET vectors)"
else
    print_fail "No feature vectors in api.features topic (streaming may not be working)"
fi

# ============================================
# WEEK 2: InfluxDB
# ============================================
print_header "WEEK 2: InfluxDB"

print_test "Checking InfluxDB connection..."
INFLUX_HEALTH=$(curl -s http://localhost:8086/health)
if echo "$INFLUX_HEALTH" | grep -q "pass"; then
    print_pass "InfluxDB is healthy"
else
    print_fail "InfluxDB health check failed"
fi

print_test "Checking for api_features measurement in InfluxDB..."
INFLUX_QUERY=$(curl -s "http://localhost:8086/api/v2/query?org=sentinel" \
  -H "Authorization: Token sentinel-influx-admin-token" \
  -H "Content-Type: application/vnd.flux" \
  -d 'from(bucket:"sentinel-metrics") |> range(start:-1h) |> filter(fn: (r) => r._measurement == "api_features") |> limit(n:1)' 2>/dev/null)

if echo "$INFLUX_QUERY" | grep -q "api_features"; then
    print_pass "InfluxDB has api_features data"
else
    print_fail "No api_features data in InfluxDB"
fi

# ============================================
# WEEK 3: ML Service
# ============================================
print_header "WEEK 3: ML Service"

print_test "Checking if ml-service exists..."
if docker ps --format '{{.Names}}' | grep -q "sentinel-ml-service"; then
    print_pass "ML service is defined"
    
    print_test "Checking ml-service health..."
    if docker ps --format '{{.Names}} {{.Status}}' | grep -q "sentinel-ml-service.*Up"; then
        print_pass "ML service is running"
        
        print_test "Testing ML service /predict endpoint..."
        ML_PREDICT=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/predict \
          -H "Content-Type: application/json" \
          -d '{"features":[0.5,0.5,0.5,0.5,12,0,0,15,10,11,11,11,15,20,30,35,10,10,0.1,0.8,0.5,0.5,1,0.5,1,0]}' 2>/dev/null)
        if [ "$ML_PREDICT" = "200" ]; then
            print_pass "ML service /predict endpoint responding ($ML_PREDICT)"
        else
            print_fail "ML service /predict returned $ML_PREDICT"
        fi
    else
        print_fail "ML service is NOT running"
    fi
else
    print_fail "ML service not found (Week 3 not implemented)"
fi

# ============================================
# WEEK 4: Monitoring
# ============================================
print_header "WEEK 4: Monitoring & Observability"

print_test "Checking Prometheus..."
PROM_HEALTH=$(curl -s http://localhost:9090/-/healthy)
if [ "$PROM_HEALTH" = "Prometheus Server is Healthy." ]; then
    print_pass "Prometheus is healthy"
else
    print_fail "Prometheus health check failed"
fi

print_test "Checking Grafana..."
GRAFANA_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health)
if [ "$GRAFANA_HEALTH" = "200" ]; then
    print_pass "Grafana is healthy"
else
    print_fail "Grafana returned $GRAFANA_HEALTH"
fi

print_test "Checking Grafana dashboards..."
if [ -f "infra/grafana/dashboards/sentinel.json" ]; then
    print_pass "Grafana dashboard file exists"
else
    print_fail "Grafana dashboard file not found"
fi

# ============================================
# SUMMARY
# ============================================
print_header "VALIDATION SUMMARY"

TOTAL=$((PASS + FAIL))
PASS_RATE=$(echo "scale=1; $PASS * 100 / $TOTAL" | bc)

echo -e "${GREEN}PASSED: $PASS${NC}"
echo -e "${RED}FAILED: $FAIL${NC}"
echo -e "TOTAL:  $TOTAL"
echo -e "Success Rate: ${PASS_RATE}%\n"

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! Sentinel is fully operational!${NC}\n"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Review the output above.${NC}\n"
    exit 1
fi
