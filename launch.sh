#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║             SENTINEL — Production Launch System                 ║
# ║       Intelligent API Observability & Auto-Scaling Platform     ║
# ╚══════════════════════════════════════════════════════════════════╝

set -e

# ─── Colors & Symbols ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

TICK="✓"
CROSS="✗"
ARROW="→"
ROCKET="🚀"
GEAR="⚙️"
CHECK="✅"
WARN="⚠️"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Banner ──────────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │                                                     │"
    echo "  │   ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗  │"
    echo "  │   ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║  │"
    echo "  │   ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║  │"
    echo "  │   ╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║  │"
    echo "  │   ███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║  │"
    echo "  │   ╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝│"
    echo "  │                                                     │"
    echo "  │    Intelligent API Observability & Auto-Scaling      │"
    echo "  │                                                     │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

step() {
    echo -e "\n${BLUE}${BOLD}[$1/${TOTAL_STEPS}]${NC} ${BOLD}$2${NC}"
    echo -e "${DIM}$(printf '%.0s─' {1..55})${NC}"
}

ok()   { echo -e "  ${GREEN}${TICK}${NC} $1"; }
fail() { echo -e "  ${RED}${CROSS}${NC} $1"; }
info() { echo -e "  ${CYAN}${ARROW}${NC} $1"; }
warn() { echo -e "  ${YELLOW}${WARN}${NC}  $1"; }

TOTAL_STEPS=7

# ═════════════════════════════════════════════════════════════════
banner

# ─── STEP 1: System Prerequisites ───────────────────────────────
step 1 "System Prerequisites"

# Docker
if docker info > /dev/null 2>&1; then
    ok "Docker daemon running ($(docker --version | awk '{print $3}' | tr -d ','))"
else
    fail "Docker is not running. Please start Docker Desktop and retry."
    exit 1
fi

# Docker Compose
if docker compose version > /dev/null 2>&1; then
    ok "Docker Compose available"
else
    fail "Docker Compose not found."
    exit 1
fi

# Python 3
if command -v python3 &> /dev/null; then
    ok "Python $(python3 --version 2>&1 | awk '{print $2}')"
else
    fail "Python 3 not found."
    exit 1
fi

# Available memory
TOTAL_MEM=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
TOTAL_MEM_GB=$(echo "scale=1; $TOTAL_MEM / 1073741824" | bc 2>/dev/null || echo "?")
if [ "$TOTAL_MEM" -gt 4000000000 ] 2>/dev/null; then
    ok "System memory: ${TOTAL_MEM_GB} GB"
else
    warn "Low memory detected (${TOTAL_MEM_GB} GB). Sentinel needs ~3 GB."
fi

# ─── STEP 2: ML Models ──────────────────────────────────────────
step 2 "ML Model Verification"

MODELS_DIR="ml-service/models"
MODELS_OK=true
for model in xgb_model.json xgb_lower.json xgb_upper.json isolation_forest.pkl; do
    if [ -f "$MODELS_DIR/$model" ]; then
        SIZE=$(du -h "$MODELS_DIR/$model" 2>/dev/null | awk '{print $1}')
        ok "$model ($SIZE)"
    else
        fail "$model missing"
        MODELS_OK=false
    fi
done

if [ "$MODELS_OK" = false ]; then
    info "Training ML models (this takes ~2 minutes)..."
    if python3 scripts/train_models.py 2>/dev/null; then
        ok "ML models trained successfully (host Python)"
    else
        warn "Host Python missing dependencies — training inside Docker..."
        docker compose build ml-service > /dev/null 2>&1 || true
        docker compose run --rm --no-deps \
            -v "$(pwd):/project" \
            -w /project \
            --user root \
            ml-service python3 scripts/train_models.py
        if [ $? -eq 0 ]; then
            ok "ML models trained successfully (Docker)"
        else
            fail "ML model training failed"
            exit 1
        fi
    fi
fi

# ─── STEP 3: Clean Up Existing Containers ───────────────────────
step 3 "Cleaning Up Existing Containers"

info "Stopping any existing Sentinel containers..."
docker compose down --remove-orphans 2>/dev/null || true
docker stop sentinel-orchestrator 2>/dev/null || true
docker rm sentinel-orchestrator 2>/dev/null || true
ok "Cleanup complete"

# ─── STEP 4: Build & Start Services ─────────────────────────────
step 4 "Building & Starting Services"

info "Starting all 9 services..."
docker compose --env-file .env up -d --build 2>&1 | tail -5 || \
  docker compose up -d --build 2>&1 | tail -5 || \
  { warn "docker compose failed, trying with --env-file /dev/null..."; \
    docker compose --env-file /dev/null up -d --build 2>&1 | tail -5; }

ok "Docker Compose up command issued"

# Wait for services
info "Waiting for services to initialize (30s)..."
sleep 30

# ─── STEP 5: Health Checks ──────────────────────────────────────
step 5 "Service Health Checks"

SERVICES_OK=0
SERVICES_TOTAL=9

check_service() {
    local name=$1
    if docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -q "sentinel-$name.*Up"; then
        ok "sentinel-$name is running"
        SERVICES_OK=$((SERVICES_OK + 1))
    else
        fail "sentinel-$name is NOT running"
    fi
}

for svc in gateway kafka redis influxdb postgres orchestrator ml-service prometheus grafana; do
    check_service "$svc"
done

echo ""
if [ "$SERVICES_OK" -eq "$SERVICES_TOTAL" ]; then
    ok "${BOLD}All $SERVICES_TOTAL services running!${NC}"
else
    warn "Only $SERVICES_OK/$SERVICES_TOTAL services running"
fi

# Endpoint health checks
echo ""
info "Checking service endpoints..."

GW_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null)
[ "$GW_HEALTH" = "200" ] && ok "Gateway /health: 200" || fail "Gateway /health: $GW_HEALTH"

ML_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
[ "$ML_HEALTH" = "200" ] && ok "ML Service /health: 200" || fail "ML Service /health: $ML_HEALTH"

INFLUX_HEALTH=$(curl -s http://localhost:8086/health 2>/dev/null | grep -c "pass")
[ "$INFLUX_HEALTH" -gt 0 ] && ok "InfluxDB: healthy" || fail "InfluxDB: unhealthy"

PROM_HEALTH=$(curl -s http://localhost:9090/-/healthy 2>/dev/null | grep -c "Healthy")
[ "$PROM_HEALTH" -gt 0 ] && ok "Prometheus: healthy" || fail "Prometheus: unhealthy"

GRAFANA_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health 2>/dev/null)
[ "$GRAFANA_HEALTH" = "200" ] && ok "Grafana: healthy" || fail "Grafana: $GRAFANA_HEALTH"

# ─── STEP 6: Validation ─────────────────────────────────────────
step 6 "Running Validation Suite"

info "Executing 30-point validation..."
echo ""
if bash scripts/validate_sentinel.sh 2>&1 | tee /tmp/sentinel_validation.txt | tail -15; then
    PASS_RATE=$(grep "Success Rate" /tmp/sentinel_validation.txt | grep -o '[0-9.]*%')
    echo ""
    ok "${BOLD}Validation: ${PASS_RATE}${NC}"
else
    warn "Some validation tests failed. Check output above."
fi

# ─── STEP 7: Launch Complete ────────────────────────────────────
step 7 "Launch Complete"

echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║           ${ROCKET}  SENTINEL IS LIVE!  ${ROCKET}                  ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║                                                      ║"
echo "  ║   Service              URL                           ║"
echo "  ║   ─────────────────    ──────────────────────────     ║"
echo "  ║   API Gateway          http://localhost:8080          ║"
echo "  ║   ML Service           http://localhost:8000          ║"
echo "  ║   Orchestrator         http://localhost:8090          ║"
echo "  ║   Grafana Dashboard    http://localhost:3000          ║"
echo "  ║   Prometheus           http://localhost:9090          ║"
echo "  ║   InfluxDB             http://localhost:8086          ║"
echo "  ║                                                      ║"
echo "  ║   Grafana Login:  admin / sentinel                   ║"
echo "  ║                                                      ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║                                                      ║"
echo "  ║   Quick Start:                                       ║"
echo "  ║     bash scripts/demo.sh     Run live demo           ║"
echo "  ║     bash scripts/validate_sentinel.sh   Run tests    ║"
echo "  ║                                                      ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"