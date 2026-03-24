#!/bin/bash
# scripts/demo.sh — Sentinel Live Demo

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}=== SENTINEL LIVE DEMO — AI-Powered API Auto-Scaling ===${NC}\n"

# 1. Check if services are healthy
echo -e "${CYAN}Checking if services are healthy...${NC}"
HEALTHY=true
# 1 Gateway
if ! curl -s http://localhost:8080/health | grep -q "ok"; then HEALTHY=false; fi
# 2 ML service
if ! curl -s http://localhost:8000/health | grep -q "status"; then HEALTHY=false; fi
# 3 Orchestrator
if ! curl -s http://localhost:8090/actuator/health | grep -q "UP"; then HEALTHY=false; fi
# 4 InfluxDB
if ! curl -s http://localhost:8086/health | grep -i -q "pass"; then HEALTHY=false; fi
# 5 Kafka Topic Check
if ! docker exec sentinel-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "api.events"; then HEALTHY=false; fi

if [ "$HEALTHY" = false ]; then
    echo -e "${RED}Some services are not healthy or ready. Run ./scripts/validate_sentinel.sh to diagnose.${NC}"
    exit 1
fi
echo -e "${GREEN}All core services are healthy!${NC}"

# 2. Check hey
if ! command -v hey >/dev/null 2>&1; then
    echo -e "${YELLOW}hey not found. Installing via brew...${NC}"
    brew install hey || exit 1
fi

# 3. Generate Token
if ! command -v python3 >/dev/null 2>&1; then echo "python3 required"; exit 1; fi
if [ -f /tmp/sentinel-venv/bin/activate ]; then source /tmp/sentinel-venv/bin/activate; fi
TOKEN=$(python3 scripts/generate_jwt.py 2>/dev/null | tr -d '[:space:]')
if [ -z "$TOKEN" ]; then
    # Fallback if the script needs a client parameter
    TOKEN=$(python3 scripts/generate_jwt.py --client-id demo-client 2>/dev/null | tr -d '[:space:]')
fi

# 4. Starting sequence
echo -e "\n${BOLD}${GREEN}Open http://localhost:3000 (admin/sentinel) to watch Grafana${NC}\n"

countdown() {
    local phase=$1
    local dur=$2
    local query_desc=$3
    echo -e "${CYAN}=== Phase $phase: $query_desc ===${NC}"
    for (( i=dur; i>0; i-- )); do
        printf "\r${YELLOW}Time remaining: %2ds${NC}" "$i"
        sleep 1
    done
    echo -e "\n"
}

# 5. Execute Load Phases

# Phase 1: Baseline 100 req/s for 30s
# hey -z 30s -q 2 -c 50 = 100 rps total approx
hey -z 30s -q 2 -c 50 -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test > /dev/null 2>&1 &
PID1=$!
countdown 1 30 "Baseline (100 req/s)"
wait $PID1

# Phase 2: Surge 3000 req/s for 60s
echo -e "${BOLD}${RED}>>> SURGE INITIATED. WATCH GRAFANA NOW. <<<${NC}"
hey -z 60s -c 200 -q 15 -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test > /dev/null 2>&1 &
PID2=$!
countdown 2 60 "Surge (3000 req/s)"
wait $PID2

# Phase 3: Recovery 100 req/s for 20s
hey -z 20s -q 2 -c 50 -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test > /dev/null 2>&1 &
PID3=$!
countdown 3 20 "Recovery (100 req/s)"
wait $PID3

echo -e "${CYAN}Fetch Action Decisions...${NC}"
ACTIONS_JSON=$(curl -s http://localhost:8090/api/actions)

DISPATCH_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"actionType":"DISPATCH"' | wc -l | tr -d ' ')
HOLD_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"actionType":"HOLD"' | wc -l | tr -d ' ')

echo -e "\n${BOLD}=== LAST 5 SCALING DECISIONS ===${NC}"
# Use python to format the JSON explicitly into last 5 
echo "$ACTIONS_JSON" | python3 << 'EOF'
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for item in data[-5:]:
            print(f"[{item.get('timestamp', '')}] ACTION: {item.get('actionType')} | CONFIDENCE: {item.get('confidence', 0):.2f} | RATE: {item.get('predictedRate', 0):.0f} | REASON: {item.get('reason')}")
    else:
        print("No valid actions returned.")
except Exception as e:
    print(f"Could not parse actions: {e}")
EOF

echo -e "\n${BOLD}${GREEN}=== SUMMARY ===${NC}"
echo -e "Total Requests: ~185,000"
echo -e "Total DISPATCH actions: ${BOLD}${DISPATCH_COUNT}${NC}"
echo -e "Total HOLD actions:     ${BOLD}${HOLD_COUNT}${NC}"

echo -e "\n${BOLD}${GREEN}Demo complete.${NC}\n"
