#!/bin/bash
# fix_influx_bucket.sh — Fix InfluxDB Bucket Issue

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== FIXING INFLUXDB BUCKET ===${NC}\n"

# 1. Get the InfluxDB token
INFLUX_TOKEN="${INFLUX_TOKEN:-sentinel-influx-admin-token}"
INFLUX_ORG="sentinel"
INFLUX_BUCKET="sentinel-metrics"

# 2. Wait for InfluxDB to be ready
echo -e "${CYAN}Waiting for InfluxDB to be ready...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8086/health | grep -i -q "pass"; then
        echo -e "${GREEN}InfluxDB is healthy!${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# 3. Check if bucket already exists
echo -e "\n${CYAN}Checking if bucket exists...${NC}"
BUCKET_CHECK=$(curl -s -H "Authorization: Token $INFLUX_TOKEN" \
  "http://localhost:8086/api/v2/buckets?org=$INFLUX_ORG&name=$INFLUX_BUCKET")

if echo "$BUCKET_CHECK" | grep -q "\"name\":\"$INFLUX_BUCKET\""; then
    echo -e "${GREEN}Bucket '$INFLUX_BUCKET' already exists!${NC}"
else
    echo -e "${YELLOW}Bucket '$INFLUX_BUCKET' not found. Creating it now...${NC}"
    
    # 4. Create the bucket
    CREATE_RESPONSE=$(curl -s -X POST http://localhost:8086/api/v2/buckets \
      -H "Authorization: Token $INFLUX_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"orgID\": \"$(curl -s -H "Authorization: Token $INFLUX_TOKEN" http://localhost:8086/api/v2/orgs | grep -o '\"id\":\"[^\"]*\"' | head -1 | cut -d'"' -f4)\",
        \"name\": \"$INFLUX_BUCKET\",
        \"retentionRules\": [{\"type\": \"expire\", \"everySeconds\": 2592000}]
      }")
    
    if echo "$CREATE_RESPONSE" | grep -q "\"name\":\"$INFLUX_BUCKET\""; then
        echo -e "${GREEN}✓ Successfully created bucket '$INFLUX_BUCKET'${NC}"
    else
        echo -e "${RED}✗ Failed to create bucket. Response:${NC}"
        echo "$CREATE_RESPONSE" | head -5
        exit 1
    fi
fi

# 5. Trigger some traffic to generate metrics
echo -e "\n${CYAN}Triggering sample traffic to generate metrics...${NC}"
if command -v python3 >/dev/null 2>&1; then
    TOKEN=$(python3 scripts/generate_jwt.py --client-id fix-test 2>/dev/null | tr -d '[:space:]')
    
    if [ -n "$TOKEN" ]; then
        echo "Sending 10 test requests..."
        for i in {1..10}; do
            curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test > /dev/null 2>&1
            echo -n "."
        done
        echo ""
        echo -e "${GREEN}Test requests sent!${NC}"
    fi
fi

# 6. Wait for metrics to appear
echo -e "\n${CYAN}Waiting for metrics to appear (5 seconds)...${NC}"
sleep 5

# 7. Verify data exists
echo -e "\n${CYAN}Verifying data in bucket...${NC}"
QUERY='from(bucket:"sentinel-metrics") |> range(start:-5m) |> limit(n:1)'
RESULT=$(curl -s -X POST http://localhost:8086/api/v2/query?org=$INFLUX_ORG \
  -H "Authorization: Token $INFLUX_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -d "$QUERY")

if [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"error"'; then
    echo -e "${GREEN}✓ Data exists in bucket!${NC}"
else
    echo -e "${YELLOW}⚠ No data yet, but bucket is created. Services should start writing soon.${NC}"
fi

echo -e "\n${GREEN}=== FIX COMPLETE ===${NC}"
