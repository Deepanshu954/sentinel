#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║                     SENTINEL — Live Demo                        ║
# ╚══════════════════════════════════════════════════════════════════╝

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "\n${CYAN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║           SENTINEL — Live Demo                   ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════╝${NC}\n"

# ── Step 1: Generate JWT ─────────────────────────────────────────
echo -e "${BLUE}${BOLD}[1/5]${NC} ${BOLD}Generating JWT Token${NC}"
echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"

TOKEN=$(python3 scripts/generate_jwt.py --client-id demo-user 2>/dev/null | tr -d '[:space:]')
if [ -n "$TOKEN" ]; then
    echo -e "  ${GREEN}✓${NC} JWT generated: ${DIM}${TOKEN:0:40}...${NC}"
else
    echo -e "  ${RED}✗${NC} JWT generation failed"
    exit 1
fi

# ── Step 2: Send Test Requests ───────────────────────────────────
echo -e "\n${BLUE}${BOLD}[2/5]${NC} ${BOLD}Sending 30 API Requests${NC}"
echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"

SUCCESS=0
FAILED=0
for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        http://localhost:8080/api/test 2>/dev/null)
    if [ "$STATUS" = "200" ] || [ "$STATUS" = "502" ]; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    printf "\r  Sending request %d/30... " "$i"
    sleep 0.1
done
echo ""
echo -e "  ${GREEN}✓${NC} ${SUCCESS} succeeded, ${FAILED} failed (502 = auth passed, no upstream)"

# ── Step 3: Kafka Metrics ────────────────────────────────────────
echo -e "\n${BLUE}${BOLD}[3/5]${NC} ${BOLD}Kafka Pipeline Status${NC}"
echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"

EVENTS=$(docker exec sentinel-kafka kafka-get-offsets --bootstrap-server localhost:9092 --topic api.events 2>/dev/null | awk -F: '{print $3}')
FEATURES=$(docker exec sentinel-kafka kafka-get-offsets --bootstrap-server localhost:9092 --topic api.features 2>/dev/null | awk -F: '{print $3}')

echo -e "  ${GREEN}✓${NC} api.events:   ${BOLD}${EVENTS:-0}${NC} messages"
echo -e "  ${GREEN}✓${NC} api.features: ${BOLD}${FEATURES:-0}${NC} feature vectors"

TOPICS=$(docker exec sentinel-kafka kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null | grep -v "^__" | sort)
echo -e "  ${CYAN}→${NC} Topics: $(echo $TOPICS | tr '\n' ', ')"

# ── Step 4: ML Prediction ────────────────────────────────────────
echo -e "\n${BLUE}${BOLD}[4/5]${NC} ${BOLD}ML Service Prediction${NC}"
echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"

PREDICT=$(curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features":[0.707,0.707,0.0,1.0,12.0,0.0,0.0,20.0,100.0,95.0,90.0,85.0,5.5,6.0,150.0,160.0,92.0,94.0,0.15,0.75,65.5,70.2,200.0,0.88,2.0,5.0]}' 2>/dev/null)

if echo "$PREDICT" | grep -q "predicted_req_rate"; then
    PRED_RATE=$(echo "$PREDICT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['predicted_req_rate']:.2f}\")" 2>/dev/null)
    CONFIDENCE=$(echo "$PREDICT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['confidence']:.4f}\")" 2>/dev/null)
    ACTION=$(echo "$PREDICT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['action'])" 2>/dev/null)
    LOWER=$(echo "$PREDICT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['lower_bound']:.2f}\")" 2>/dev/null)
    UPPER=$(echo "$PREDICT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['upper_bound']:.2f}\")" 2>/dev/null)

    echo -e "  ${GREEN}✓${NC} Predicted Rate:  ${BOLD}${PRED_RATE}${NC} req/s"
    echo -e "  ${GREEN}✓${NC} Bounds:          [${LOWER}, ${UPPER}]"
    echo -e "  ${GREEN}✓${NC} Confidence:      ${BOLD}${CONFIDENCE}${NC}"
    if [ "$ACTION" = "DISPATCH" ]; then
        echo -e "  ${GREEN}✓${NC} Decision:        ${GREEN}${BOLD}${ACTION}${NC} — scaling recommended"
    else
        echo -e "  ${YELLOW}✓${NC} Decision:        ${YELLOW}${BOLD}${ACTION}${NC} — holding steady"
    fi
else
    echo -e "  ${RED}✗${NC} Prediction failed: $PREDICT"
fi

# ── Step 5: Anomaly Detection ────────────────────────────────────
echo -e "\n${BLUE}${BOLD}[5/5]${NC} ${BOLD}Anomaly Detection${NC}"
echo -e "${DIM}$(printf '%.0s─' {1..50})${NC}"

ANOMALY=$(curl -s -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"features":[50,50,50,50,120,0,0,150,1000,900,800,700,55,60,1500,1600,920,940,1.5,7.5,95.5,92.2,2000,0.2,10.0,50.0]}' 2>/dev/null)

if echo "$ANOMALY" | grep -q "is_anomaly"; then
    IS_ANOM=$(echo "$ANOMALY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['is_anomaly'])" 2>/dev/null)
    SCORE=$(echo "$ANOMALY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['anomaly_score']:.4f}\")" 2>/dev/null)
    INTERP=$(echo "$ANOMALY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['interpretation'])" 2>/dev/null)

    if [ "$IS_ANOM" = "True" ]; then
        echo -e "  ${RED}⚠${NC}  Anomaly:  ${RED}${BOLD}DETECTED${NC}"
    else
        echo -e "  ${GREEN}✓${NC} Anomaly:  ${GREEN}${BOLD}NOT DETECTED${NC}"
    fi
    echo -e "  ${CYAN}→${NC} Score: ${SCORE}  Interpretation: ${BOLD}${INTERP}${NC}"
else
    echo -e "  ${RED}✗${NC} Anomaly detection failed"
fi

# ── Summary ──────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║              Demo Complete!                       ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║  Dashboard:  ${NC}${BOLD}http://localhost:3000${GREEN}${BOLD}                ║${NC}"
echo -e "${GREEN}${BOLD}║  Login:      ${NC}${BOLD}admin / sentinel${GREEN}${BOLD}                    ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}\n"
