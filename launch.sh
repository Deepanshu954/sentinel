#!/bin/bash
# launch.sh — Launch Sentinel Environment

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}=== LAUNCHING SENTINEL ===${NC}\n"
start_time=$(date +%s)

fail() { echo -e "${RED}✗ FAIL${NC} $1"; exit 1; }
ok()   { echo -e "${GREEN}✓ PASS${NC} $1"; }
warn() { echo -e "${YELLOW}⚠ WARN${NC} $1"; }

# 1. Check docker-compose
if ! command -v docker-compose >/dev/null 2>&1; then
    fail "docker-compose not found. Run scripts/build.sh first."
fi

# 2. Check variables
if [ ! -f ".env.example" ]; then
    fail "Missing .env.example file. Root source is required."
fi

# 3. Check ML Models Output
echo -e "${CYAN}Verifying ML predictive models are present...${NC}"
if [ ! -f "ml-service/model_weights/xgb_model.json" ] || [ ! -f "ml-service/model_weights/isolation_forest.pkl" ]; then
    echo -e "${RED}ERROR: ML models missing. You must run ./scripts/train.sh first to compile predictors.${NC}"
    exit 1
fi

echo -e "\n${CYAN}Starting docker containers...${NC}"

# 4. Silent Down
docker-compose down --remove-orphans 2>/dev/null || true

# 5. Up
DOCKER_BUILDKIT=0 docker-compose --env-file .env up -d --build || fail "Failed to start containers"

# 6. Health wait loop (max 45s, checking every 2s)
echo -e "\n${CYAN}Waiting for services to become healthy...${NC}"
max_attempts=22
attempt=1

while [ $attempt -le $max_attempts ]; do
    # Get all 9 status lines
    raw_status=$(docker-compose ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}" | tail -n +2)
    service_count=$(echo "$raw_status" | wc -l | tr -d ' ')
    
    # We want 9 services. They must either contain "Up" or "healthy".
    # Since state varies, we check if ANY service is 'restarting' or 'exited'.
    if echo "$raw_status" | grep -i -q "restarting\|exited"; then
        # Services crashing
        fail "One or more services crashed.\n$raw_status"
    fi

    # Check if all 9 are Up and any healthchecks are not 'unhealthy' or 'starting'
    if [ "$service_count" -ge 9 ] && ! echo "$raw_status" | grep -i -q "starting\|unhealthy"; then
        echo -e "${GREEN}All services are up and healthy!${NC}"
        break
    fi

    # 6B. Check ML Models Loaded
    ML_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null | grep -o '"models_loaded": *true' || echo "down")
    if [ "$ML_HEALTH" != "down" ]; then
        echo -e "  [${GREEN}OK${NC}] ML predictors fully loaded in memory"
        break
    fi

    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo -e "\n${RED}Timed out waiting for services.${NC}"
    docker-compose ps
    exit 1
fi

end_time=$(date +%s)
duration=$((end_time - start_time))

# 7. Print URLs
echo -e "\n${GREEN}${BOLD}=== SENTINEL IS LIVE (in ${duration}s) ===${NC}"
echo -e "
${BOLD}Core Services:${NC}
- API Gateway:    http://localhost:8080/health
- Orchestrator:   http://localhost:8090/actuator/health
- ML Service:     http://localhost:8000/docs

${BOLD}Observability (Credentials):${NC}
- Grafana:        http://localhost:3000   (admin / sentinel)
- InfluxDB:       http://localhost:8086   (admin / sentinel-influx-admin-token)
- Prometheus:     http://localhost:9090
"

# 8. Final instructions
echo -e "${YELLOW}${BOLD}Run scripts/validate_sentinel.sh to verify everything works${NC}\n"