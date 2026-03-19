#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}       Sentinel Platform Launcher      ${NC}"
echo -e "${BLUE}=======================================${NC}"

# Pre-flight Checks
echo "Running pre-flight checks..."
command -v mvn >/dev/null 2>&1 || { echo -e "${RED}Error: Maven (mvn) is required but not installed.${NC} Aborting."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}Error: docker-compose is required but not installed.${NC} Aborting."; exit 1; }

echo -e "\n${GREEN}[1/3] Building Orchestrator (Spring Boot Java JAR)...${NC}"
cd orchestrator
mvn clean package -DskipTests
cd ..

echo -e "\n${GREEN}[2/3] Building and Starting Docker Services...${NC}"
# Gracefully shut down previous instances
docker-compose down || true

# Start and force rebuild of images (Gateway, ML-Service, Orchestrator)
docker-compose up -d --build

echo -e "\n${GREEN}[3/3] Verifying Container Boot...${NC}"
sleep 10
docker-compose ps

echo -e "\n${BLUE}=======================================${NC}"
echo -e "${GREEN}      All Services Started Successfully!     ${NC}"
echo -e "${BLUE}=======================================${NC}"
echo "Local Endpoints available:"
echo " 🌐 API Gateway: http://localhost:8080"
echo " 📊 Grafana:     http://localhost:3000 (User: admin / Pass: sentinel)"
echo " 🗄️ InfluxDB:    http://localhost:8086"
echo " 📈 Prometheus:  http://localhost:9090"
echo ""
echo "To run integration tests, execute:"
echo "   chmod +x scripts/test_week2.sh && ./scripts/test_week2.sh"
echo "To view live logs for the orchestrator, execute:"
echo "   docker-compose logs -f orchestrator"
echo -e "${BLUE}=======================================${NC}"
