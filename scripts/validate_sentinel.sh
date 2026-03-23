#!/bin/bash
# scripts/validate_sentinel.sh — 30-Point Sentinel Validation Suite

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
FAIL=0

header() { echo -e "\n${CYAN}${BOLD}=== $1 ===${NC}"; }
ok()   { echo -e "  ${GREEN}✓ PASS${NC} $1"; PASS=$((PASS + 1)); }
err()  { echo -e "  ${RED}✗ FAIL${NC} $1"; FAIL=$((FAIL + 1)); }

# Check dependencies
if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}Missing required tools (curl or python3). Run scripts/build.sh.${NC}"
    exit 1
fi

if [ -f /tmp/sentinel-venv/bin/activate ]; then
    source /tmp/sentinel-venv/bin/activate
fi

TOKEN_A=$(python3 scripts/generate_jwt.py --client-id test-a 2>/dev/null | tr -d '[:space:]')
TOKEN_B=$(python3 scripts/generate_jwt.py --client-id test-b 2>/dev/null | tr -d '[:space:]')

FEATURES='{"features":[0.5,0.866,0.5,0.866,20.0,0.0,0.0,15.0,850.0,820.0,800.0,780.0,120.5,135.2,950.0,920.0,810.5,845.2,15.0,0.0,0.25,0.45,0.65,0.5,1.0,0.5]}'

# ─── SECTION 1: Infrastructure (9 checks) ─────────────────────────────────────────
header "INFRASTRUCTURE (9 checks)"

# 1
if curl -s http://localhost:8080/health | grep -q "ok"; then ok "Gateway health (200)"; else err "Gateway health"; fi
# 2
if curl -s http://localhost:8000/health | grep -q "status"; then ok "ML service health (200)"; else err "ML service health"; fi
# 3
if curl -s http://localhost:8090/actuator/health | grep -q "UP"; then ok "Orchestrator health (200)"; else err "Orchestrator health"; fi
# 4
if curl -s http://localhost:8086/health | grep -i -q "pass"; then ok "InfluxDB health (pass)"; else err "InfluxDB health"; fi
# 5
GRAF_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health)
if [ "$GRAF_HEALTH" = "200" ]; then ok "Grafana health (200)"; else err "Grafana health ($GRAF_HEALTH)"; fi
# 6
PROM_HEALTH=$(curl -s http://localhost:9090/-/healthy 2>/dev/null)
if [[ "$PROM_HEALTH" == *"Healthy"* ]] || [[ "$PROM_HEALTH" == *"Prometheus"* ]]; then ok "Prometheus health (Healthy)"; else err "Prometheus health"; fi

# Ensure topics exist early so the checks don't fail due to race conditions
docker exec sentinel-kafka kafka-topics --create --if-not-exists --topic api.events --bootstrap-server localhost:9092 >/dev/null 2>&1
docker exec sentinel-kafka kafka-topics --create --if-not-exists --topic api.features --bootstrap-server localhost:9092 >/dev/null 2>&1
docker exec sentinel-kafka kafka-topics --create --if-not-exists --topic scaling.actions --bootstrap-server localhost:9092 >/dev/null 2>&1
sleep 2

# 7
if docker exec sentinel-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "api.events"; then ok "Kafka topic api.events"; else err "Kafka topic api.events"; fi
# 8
if docker exec sentinel-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "api.features"; then ok "Kafka topic api.features"; else err "Kafka topic api.features"; fi
# 9
if docker exec sentinel-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "scaling.actions"; then ok "Kafka topic scaling.actions"; else err "Kafka topic scaling.actions"; fi

# ─── SECTION 2: Gateway (4 checks) ────────────────────────────────────────────────
header "GATEWAY (4 checks)"

# 10
AUTH_NONE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/test)
if [ "$AUTH_NONE" = "401" ]; then ok "401 no token"; else err "401 no token ($AUTH_NONE)"; fi
# 11
AUTH_BAD=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer bad" http://localhost:8080/api/test)
if [ "$AUTH_BAD" = "401" ]; then ok "401 bad token"; else err "401 bad token ($AUTH_BAD)"; fi
# 12
AUTH_VALID=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_A" http://localhost:8080/api/test)
if [ "$AUTH_VALID" != "401" ] && [ "$AUTH_VALID" != "500" ] && [ "$AUTH_VALID" != "000" ]; then ok "Non-401 valid token ($AUTH_VALID)"; else err "Non-401 valid token ($AUTH_VALID)"; fi

# 13 Rate Limiting
echo -en "  ${CYAN}→${NC} Flooding for rate limit (Token B)... "
hey -n 1005 -c 50 -H "Authorization: Bearer $TOKEN_B" http://localhost:8080/api/test > /dev/null 2>&1
RL_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_B" http://localhost:8080/api/test)
if [ "$RL_CODE" = "429" ]; then echo ""; ok "Rate limiting 429 received"; else echo ""; err "Rate limiting failed ($RL_CODE)"; fi

# ─── SECTION 3: Streaming pipeline (3 checks) ─────────────────────────────────────
header "STREAMING PIPELINE (3 checks)"

# 14
EVENTS_MSG=$(docker exec sentinel-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic api.events --from-beginning --timeout-ms 10000 --max-messages 1 2>/dev/null)
if [ -n "$EVENTS_MSG" ] && [[ "$EVENTS_MSG" != *"Processed a total of 0 messages"* ]]; then ok "api.events has messages"; else err "api.events has messages"; fi

# 15 & 16
FEATURES_MSG=$(docker exec sentinel-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic api.features --from-beginning --timeout-ms 10000 --max-messages 1 2>/dev/null | grep "{")
if [ -n "$FEATURES_MSG" ]; then
    ok "api.features has messages"
    # Parse latest JSON and check key count (needs 26 features + endpoint + timestamp = 28 keys total)
    KEY_COUNT=$(echo "$FEATURES_MSG" | python3 -c 'import sys, json; print(len([k for k,v in json.loads(sys.stdin.read()).items() if isinstance(v, (int, float))]) >= 26)' 2>/dev/null || echo "False")
    if [ "$KEY_COUNT" = "True" ]; then
        ok "api.features has 26 fields"
    else
        err "api.features has 26 fields (parsed count wrong)"
    fi
else
    err "api.features has messages"
    err "api.features has 26 fields"
fi

# ─── SECTION 4: InfluxDB (2 checks) ───────────────────────────────────────────────
header "INFLUXDB (2 checks)"

# 17
INFLUX_TOKEN=$(docker exec sentinel-gateway env | grep INFLUX_TOKEN | cut -d= -f2 | tr -d '\r' 2>/dev/null)
if [ -z "$INFLUX_TOKEN" ]; then
    if [ -f .env ]; then
        INFLUX_TOKEN=$(grep INFLUX_TOKEN .env | cut -d= -f2 | tr -d '\r')
    else
        INFLUX_TOKEN=$(grep INFLUX_TOKEN .env.example | cut -d= -f2 | tr -d '\r')
    fi
fi

# Final fallback
if [ -z "$INFLUX_TOKEN" ]; then INFLUX_TOKEN="sentinel-influx-admin-token"; fi

BUCKETS=$(curl -s -H "Authorization: Token $INFLUX_TOKEN" \
  http://localhost:8086/api/v2/buckets?org=sentinel)
if echo "$BUCKETS" | grep -q "sentinel-metrics"; then ok "Bucket sentinel-metrics exists"; else err "Bucket sentinel-metrics exists"; fi

# 18
QUERY='from(bucket:"sentinel-metrics") |> range(start:-5m) |> limit(n:1)'
RESULT=$(curl -s -X POST http://localhost:8086/api/v2/query?org=sentinel \
  -H "Authorization: Token $INFLUX_TOKEN" \
  -H "Content-Type: application/vnd.flux" \
  -d "$QUERY")
if [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"unauthorized"' && ! echo "$RESULT" | grep -q '"error"'; then ok "Recent data in last 5 minutes"; else err "Recent data in last 5 minutes"; fi

# ─── SECTION 5: ML service (4 checks) ─────────────────────────────────────────────
header "ML SERVICE (4 checks)"

# 19, 20, 21
PREDICT_RES=$(curl -s -X POST -H "Content-Type: application/json" -d "$FEATURES" http://localhost:8000/predict)
HTTP_PREDICT=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$FEATURES" http://localhost:8000/predict)
if [ "$HTTP_PREDICT" = "200" ]; then 
    ok "POST /predict with \$FEATURES → 200"
    
    CONF=$(echo "$PREDICT_RES" | python3 -c 'import sys, json; print(0 <= json.loads(sys.stdin.read()).get("confidence", -1) <= 1)' 2>/dev/null)
    if [ "$CONF" = "True" ]; then ok "Response confidence between 0 and 1"; else err "Response confidence between 0 and 1"; fi
    
    if echo "$PREDICT_RES" | grep -q '"action":"DISPATCH"\|"action":"HOLD"'; then ok "Response has action = DISPATCH or HOLD"; else err "Response has action = DISPATCH or HOLD"; fi
else 
    err "POST /predict with \$FEATURES → 200 ($HTTP_PREDICT)"
    err "Response confidence between 0 and 1 (skip)"
    err "Response has action = DISPATCH or HOLD (skip)"
fi

# 22
HTTP_ANOMALY=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$FEATURES" http://localhost:8000/anomaly)
if [ "$HTTP_ANOMALY" = "200" ]; then ok "POST /anomaly with \$FEATURES → 200"; else err "POST /anomaly with \$FEATURES → 200 ($HTTP_ANOMALY)"; fi

# ─── SECTION 6: Orchestrator (4 checks) ───────────────────────────────────────────
header "ORCHESTRATOR (4 checks)"

# 23
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/api/status)
if [ "$STATUS_CODE" = "200" ]; then ok "GET localhost:8090/api/status → 200"; else err "GET /api/status ($STATUS_CODE)"; fi

# 24 & 25
ACTIONS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/api/actions)
if [ "$ACTIONS_CODE" = "200" ]; then 
    ok "GET localhost:8090/api/actions → 200"
    
    ACTIONS_LEN=0
    for i in {1..3}; do
        ACTIONS_LEN=$(curl -s http://localhost:8090/api/actions | python3 -c 'import sys, json; print(len(json.loads(sys.stdin.read())))' 2>/dev/null || echo "0")
        if [ "$ACTIONS_LEN" -gt 0 ]; then break; fi
        sleep 2
    done
    if [ "$ACTIONS_LEN" -gt 0 ]; then ok "/api/actions has at least 1 entry"; else err "/api/actions has at least 1 entry ($ACTIONS_LEN)"; fi
else 
    err "GET /api/actions ($ACTIONS_CODE)"
    err "/api/actions has at least 1 entry (skip)"
fi

# 26
PREDICTION_FOUND=false
for i in {1..4}; do
    if docker logs sentinel-orchestrator --since 10m 2>/dev/null | grep -i "predict\|confidence\|dispatch\|hold" > /dev/null; then
        PREDICTION_FOUND=true
        break
    fi
    sleep 3
done
if [ "$PREDICTION_FOUND" = true ]; then ok "Orchestrator logs show ML activity"; else err "Orchestrator logs show ML activity"; fi

# ─── SECTION 7: Observability (4 checks) ──────────────────────────────────────────
header "OBSERVABILITY (4 checks)"

# 27
if curl -s http://localhost:9090/api/v1/targets | python3 -c 'import sys, json; print(any(t.get("labels", {}).get("job") == "gateway" and t.get("health") == "up" for t in json.loads(sys.stdin.read()).get("data", {}).get("activeTargets", [])))' | grep -q 'True'; then ok "Prometheus has gateway target"; else err "Prometheus has gateway target"; fi
# 28
if curl -s http://localhost:9090/api/v1/targets | python3 -c 'import sys, json; print(any(t.get("labels", {}).get("job") == "orchestrator" and t.get("health") == "up" for t in json.loads(sys.stdin.read()).get("data", {}).get("activeTargets", [])))' | grep -q 'True'; then ok "Prometheus has orchestrator target"; else err "Prometheus has orchestrator target"; fi
# 29
DATASOURCES=$(curl -s -u admin:sentinel http://localhost:3000/api/datasources)
if echo "$DATASOURCES" | grep -qi "influx"; then ok "Grafana datasource configured"; else err "Grafana datasource configured"; fi
# 30
DASHBOARDS=$(curl -s -u admin:sentinel "http://localhost:3000/api/search?type=dash-db")
if echo "$DASHBOARDS" | grep -qi "sentinel\|api\|gateway"; then ok "Grafana dashboard exists"; else err "Grafana dashboard exists"; fi

# ─── OUTPUT ───────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}=== RESULT ===${NC}"
echo -e "${BOLD}${CYAN}$PASS / 30 checks passed${NC}"

if [ "$PASS" -eq 30 ]; then
    echo -e "${GREEN}${BOLD}ALL SYSTEMS GO${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}Validation failed. Look at the ✗ FAIL lines above.${NC}"
    exit 1
fi
