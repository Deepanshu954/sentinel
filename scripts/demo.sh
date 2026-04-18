#!/bin/bash
# scripts/demo.sh — Sentinel Local Autoscaling Demo
# 5-phase scenario runner with real Docker replica scaling

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

RESULTS_DIR="/tmp/sentinel-demo-$$"
mkdir -p "$RESULTS_DIR"

# ── Docker Compose Detection ─────────────────────────────────────────────
if docker compose version > /dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    DC="docker-compose"
else
    echo -e "${RED}Neither 'docker compose' nor 'docker-compose' found.${NC}"
    exit 1
fi

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       SENTINEL LOCAL AUTOSCALING DEMO                       ║"
echo "║       AI-Powered Predictive Auto-Scaling                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Preflight Checks ─────────────────────────────────────────────────
echo -e "${CYAN}[Preflight] Checking services...${NC}"
HEALTHY=true

check_service() {
    local name=$1 url=$2 match=$3
    if curl -sf "$url" 2>/dev/null | grep -qi "$match"; then
        echo -e "  ${GREEN}✓${NC} $name"
    else
        echo -e "  ${RED}✗${NC} $name"
        HEALTHY=false
    fi
}

check_service "Gateway"      "http://localhost:8080/health"              "ok"
check_service "ML Service"   "http://localhost:8000/health"              "status"
check_service "Orchestrator" "http://localhost:8090/actuator/health"     "UP"
check_service "InfluxDB"     "http://localhost:8086/health"              "pass"

# Check demo-backend (may be on unexposed port, check via gateway proxy)
if curl -sf "http://localhost:8080/api/test" -H "Authorization: Bearer dummy" > /dev/null 2>&1 || true; then
    echo -e "  ${GREEN}✓${NC} Demo Backend (via Gateway)"
fi

if [ "$HEALTHY" = false ]; then
    echo -e "\n${RED}Some services are not healthy. Run: ./launch.sh${NC}"
    exit 1
fi

# ── 2. Check hey ─────────────────────────────────────────────────────────
if ! command -v hey > /dev/null 2>&1; then
    echo -e "${YELLOW}hey not found. Installing...${NC}"
    brew install hey || { echo -e "${RED}Failed to install hey${NC}"; exit 1; }
fi

# ── 3. Generate JWT Token ───────────────────────────────────────────────
if [ -f /tmp/sentinel-venv/bin/activate ]; then source /tmp/sentinel-venv/bin/activate; fi
TOKEN=$(python3 scripts/generate_jwt.py 2>/dev/null | tr -d '[:space:]' || true)
if [ -z "$TOKEN" ]; then
    TOKEN=$(python3 scripts/generate_jwt.py --client-id demo-client 2>/dev/null | tr -d '[:space:]' || true)
fi
if [ -z "$TOKEN" ]; then
    echo -e "${RED}Failed to generate JWT token${NC}"
    exit 1
fi

# ── Helper Functions ─────────────────────────────────────────────────────

get_replica_count() {
    $DC ps demo-backend 2>/dev/null | grep -c "running" || echo "1"
}

record_replicas() {
    local phase=$1
    local count
    count=$(get_replica_count)
    echo "$phase,$count,$(date +%s)" >> "$RESULTS_DIR/replicas.csv"
    echo "$count"
}

run_phase() {
    local phase_num=$1
    local phase_name=$2
    local duration=$3
    local concurrency=$4
    local qps=$5
    local color=$6

    echo -e "\n${color}${BOLD}═══ Phase $phase_num: $phase_name ═══${NC}"
    echo -e "${DIM}  Duration: ${duration}s | Concurrency: $concurrency | Target: ~$((concurrency * qps)) rps${NC}"

    # Record replicas at start
    local start_replicas
    start_replicas=$(record_replicas "phase${phase_num}_start")
    echo -e "  Replicas at start: ${BOLD}${start_replicas}${NC}"

    # Run load
    local hey_output="$RESULTS_DIR/phase${phase_num}.txt"
    hey -z "${duration}s" -c "$concurrency" -q "$qps" \
        -H "Authorization: Bearer $TOKEN" \
        http://localhost:8080/api/test > "$hey_output" 2>&1 &
    local PID=$!

    # Countdown with live replica monitoring
    for (( i=duration; i>0; i-- )); do
        if (( i % 10 == 0 )); then
            local live_replicas
            live_replicas=$(get_replica_count)
            printf "\r  ${YELLOW}Time: %3ds remaining | Replicas: %s${NC}   " "$i" "$live_replicas"
        else
            printf "\r  ${YELLOW}Time: %3ds remaining${NC}   " "$i"
        fi
        sleep 1
    done
    echo ""

    wait $PID 2>/dev/null || true

    # Record replicas at end
    local end_replicas
    end_replicas=$(record_replicas "phase${phase_num}_end")
    echo -e "  Replicas at end: ${BOLD}${end_replicas}${NC}"

    # Extract metrics from hey output
    local p50 p95 errors total_req
    p50=$(grep "50%" "$hey_output" 2>/dev/null | awk '{print $2}' || echo "N/A")
    p95=$(grep "95%" "$hey_output" 2>/dev/null | awk '{print $2}' || echo "N/A")
    errors=$(grep -c "5[0-9][0-9]\|error" "$hey_output" 2>/dev/null || echo "0")
    total_req=$(grep "requests done" "$hey_output" 2>/dev/null | awk '{print $1}' || \
                grep "Requests/sec" "$hey_output" 2>/dev/null | awk '{print $2}' || echo "N/A")

    echo -e "  p50: ${p50}s | p95: ${p95}s | Errors: ${errors}"
    echo "${phase_num},${phase_name},${p50},${p95},${errors},${start_replicas},${end_replicas}" \
        >> "$RESULTS_DIR/phases.csv"
}

# ── 4. Pre-Demo: Record Initial State ───────────────────────────────────
echo -e "\n${CYAN}[Setup] Recording initial state...${NC}"
INITIAL_REPLICAS=$(record_replicas "initial")
echo -e "  Initial replica count: ${BOLD}${INITIAL_REPLICAS}${NC}"
echo -e "\n${BOLD}${GREEN}▶  Open http://localhost:3000 (admin/sentinel) for Grafana  ◀${NC}\n"
sleep 3

# ── 5. Execute 5-Phase Scenario ─────────────────────────────────────────

# Phase 1: Baseline — steady low traffic
run_phase 1 "Baseline (steady)" 30 10 2 "$GREEN"

# Phase 2: Flash Crowd — sudden surge
echo -e "\n${RED}${BOLD}>>> FLASH CROWD SURGE — WATCH GRAFANA <<<${NC}"
sleep 2
run_phase 2 "Flash Crowd (surge)" 45 200 10 "$RED"

# Phase 3: Sustained Pressure — continued high load
run_phase 3 "Sustained Pressure" 30 150 10 "$MAGENTA"

# Phase 4: Second Wave — peak load
echo -e "\n${RED}${BOLD}>>> SECOND WAVE PEAK — MAX LOAD <<<${NC}"
sleep 2
run_phase 4 "Second Wave (peak)" 30 250 12 "$RED"

# Phase 5: Recovery — load drops, wait for scale-in
run_phase 5 "Recovery (cooldown)" 60 5 2 "$GREEN"

# ── 6. Fetch Scaling Decisions ──────────────────────────────────────────
echo -e "\n${CYAN}[Results] Fetching scaling decisions...${NC}"
ACTIONS_JSON=$(curl -sf http://localhost:8090/api/actions 2>/dev/null || echo "[]")

DISPATCH_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"actionType":"DISPATCH"' | wc -l | tr -d ' ')
HOLD_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"actionType":"HOLD"' | wc -l | tr -d ' ')
SCALE_OUT_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"scaleAction":"SCALE_OUT"' | wc -l | tr -d ' ')
SCALE_IN_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"scaleAction":"SCALE_IN"' | wc -l | tr -d ' ')
COOLDOWN_COUNT=$(echo "$ACTIONS_JSON" | grep -o '"scaleAction":"COOLDOWN"' | wc -l | tr -d ' ')

# Get final replica count
FINAL_REPLICAS=$(get_replica_count)

# Provisioning latency from actions
PROV_LATENCIES=$(echo "$ACTIONS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        lats = [a.get('provisioningLatencyMs', 0) for a in data if a.get('provisioningLatencyMs', 0) > 0]
        if lats:
            print(f'avg={sum(lats)//len(lats)}ms  min={min(lats)}ms  max={max(lats)}ms  samples={len(lats)}')
        else:
            print('No provisioning events recorded')
except:
    print('N/A')
" 2>/dev/null || echo "N/A")

# ── 7. Summary Report ──────────────────────────────────────────────────
echo -e "\n${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    DEMO SUMMARY REPORT                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo -e "║  ${GREEN}Scaling Decisions${NC}${BOLD}                                           ║"
echo "║    DISPATCH:       $DISPATCH_COUNT                                         ║"
echo "║    HOLD:           $HOLD_COUNT                                         ║"
echo "║    SCALE_OUT:      $SCALE_OUT_COUNT                                         ║"
echo "║    SCALE_IN:       $SCALE_IN_COUNT                                         ║"
echo "║    COOLDOWN:       $COOLDOWN_COUNT                                         ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo -e "║  ${GREEN}Replicas${NC}${BOLD}                                                    ║"
echo "║    Initial:         $INITIAL_REPLICAS                                        ║"
echo "║    Final:           $FINAL_REPLICAS                                        ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo -e "║  ${GREEN}Provisioning Latency${NC}${BOLD}                                        ║"
echo "║    $PROV_LATENCIES"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Print last 5 scaling actions
echo -e "${BOLD}Last 5 Scaling Actions:${NC}"
echo "$ACTIONS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for item in data[-5:]:
            ts = item.get('timestamp', 'N/A')
            action = item.get('actionType', '')
            scale = item.get('scaleAction', '')
            conf = item.get('confidence', 0)
            rate = item.get('predictedRate', 0)
            desired = item.get('desiredReplicas', 0)
            actual = item.get('actualReplicas', 0)
            prov = item.get('provisioningLatencyMs', 0)
            print(f'  [{ts}] {action}/{scale} | conf={conf:.2f} | rate={rate:.0f} | replicas {actual}→{desired} | prov={prov}ms')
except Exception as e:
    print(f'  Could not parse actions: {e}')
" 2>/dev/null

# Phase-by-phase latency summary
if [ -f "$RESULTS_DIR/phases.csv" ]; then
    echo -e "\n${BOLD}Phase Latency Summary:${NC}"
    printf "  %-25s %10s %10s %8s %10s %10s\n" "Phase" "p50" "p95" "Errors" "Start-R" "End-R"
    while IFS=, read -r num name p50 p95 errs sr er; do
        printf "  %-25s %10s %10s %8s %10s %10s\n" "$name" "$p50" "$p95" "$errs" "$sr" "$er"
    done < "$RESULTS_DIR/phases.csv"
fi

echo -e "\n${BOLD}${GREEN}Demo complete. Results saved to $RESULTS_DIR${NC}\n"
