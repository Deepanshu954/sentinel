#!/bin/bash
# scripts/test_week2.sh

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper variables
INFLUX_TOKEN="sentinel-influx-admin-token"
INFLUX_URL="http://localhost:8086"
GRAFANA_URL="http://localhost:3000"
GATEWAY_URL="http://localhost:8080"
FAIL_COUNT=0

function print_result() {
  local test_name=$1
  local status=$2
  local reason=$3
  if [ "$status" == "PASS" ]; then
    echo -e "${GREEN}[PASS]${NC} $test_name"
  else
    echo -e "${RED}[FAIL]${NC} $test_name - Reason: $reason"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

echo "Starting Sentinel Week 2 Integration Tests..."
echo "----------------------------------------------"

# 1. Gateway Health Test
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $GATEWAY_URL/health || echo "000")
if [ "$STATUS" == "200" ]; then
  print_result "Gateway Health Check" "PASS" ""
else
  print_result "Gateway Health Check" "FAIL" "Expected 200 OK, got $STATUS"
fi

# 2. Gateway Auth Test (No Token)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $GATEWAY_URL/api/test || echo "000")
if [ "$STATUS" == "401" ]; then
  print_result "Gateway Auth (No Token)" "PASS" ""
else
  print_result "Gateway Auth (No Token)" "FAIL" "Expected 401 Unauthorized, got $STATUS"
fi

# 3. Gateway Auth Test (Valid Token)
TOKEN=$(python3 scripts/generate_jwt.py | grep -Eo 'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' | head -n 1)
if [ -n "$TOKEN" ]; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" $GATEWAY_URL/api/test || echo "000")
  # 502 is acceptable if ML service is down, but Auth passed.
  if [[ "$STATUS" == "200" || "$STATUS" == "502" ]]; then
    print_result "Gateway Auth (Valid Token)" "PASS" ""
  else
    print_result "Gateway Auth (Valid Token)" "FAIL" "Expected 200 or 502, got $STATUS"
  fi
else
  print_result "Gateway Auth (Valid Token)" "FAIL" "Could not generate JWT token"
fi

echo "Waiting for data pipelines (Kafka Streams & InfluxDB) to catch up..."
sleep 3

# 4. Kafka api.events Topic Test
EVENTS_MSG=$(docker exec sentinel-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic api.events --from-beginning --max-messages 1 --timeout-ms 5000 2>/dev/null | grep "endpoint")
if [ -n "$EVENTS_MSG" ]; then
  print_result "Kafka Topic (api.events)" "PASS" ""
else
  print_result "Kafka Topic (api.events)" "FAIL" "No messages found in api.events topic within 5 seconds"
fi

# 5. Kafka api.features Topic Test
FEATURES_MSG=$(docker exec sentinel-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic api.features --from-beginning --max-messages 1 --timeout-ms 5000 2>/dev/null | grep "req_rate_1m")
if [ -n "$FEATURES_MSG" ]; then
  print_result "Kafka Topic (api.features)" "PASS" ""
else
  print_result "Kafka Topic (api.features)" "FAIL" "No messages found in api.features topic within 5 seconds"
fi

# 6. InfluxDB Data Verification
INFLUX_RESPONSE=$(curl -s -X POST $INFLUX_URL/api/v2/query?org=sentinel \
  -H "Authorization: Token $INFLUX_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -H "Accept: application/csv" \
  -d 'from(bucket:"sentinel-metrics") |> range(start:-10m) |> filter(fn:(r) => r._measurement == "api_features")')

if [[ "$INFLUX_RESPONSE" == *"/api/test"* || "$INFLUX_RESPONSE" == *"req_rate_1m"* ]]; then
  print_result "InfluxDB Data Ingestion" "PASS" ""
else
  print_result "InfluxDB Data Ingestion" "FAIL" "Query returned no matching data for api_features"
fi

# 7. Grafana Health Test
GRAFANA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $GRAFANA_URL/api/health || echo "000")
if [ "$GRAFANA_STATUS" == "200" ]; then
  print_result "Grafana Health Check" "PASS" ""
else
  print_result "Grafana Health Check" "FAIL" "Expected 200 OK, got $GRAFANA_STATUS"
fi

echo "----------------------------------------------"
if [ $FAIL_COUNT -eq 0 ]; then
  echo -e "${GREEN}ALL TESTS PASSED!${NC}"
  exit 0
else
  echo -e "${RED}$FAIL_COUNT TEST(S) FAILED.${NC}"
  exit 1
fi
