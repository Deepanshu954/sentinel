#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}       Sentinel Platform Test Suite    ${NC}"
echo -e "${BLUE}=======================================${NC}"
echo "Running all backend unit and end-to-end integration tests..."

echo -e "\n${BLUE}[1/3] Running Gateway (Go) Unit Tests...${NC}"
cd gateway
go test -v ./... || { echo -e "${RED}Gateway tests failed!${NC}"; exit 1; }
cd ..

echo -e "\n${BLUE}[2/3] Running Orchestrator (Java) Unit Tests...${NC}"
cd orchestrator
mvn test || { echo -e "${RED}Orchestrator tests failed!${NC}"; exit 1; }
cd ..

echo -e "\n${BLUE}[3/3] Running End-to-End Integration Tests...${NC}"
echo "Note: This requires the platform to be actively running via './launch.sh'"
if [ -f scripts/test_week2.sh ]; then
    chmod +x scripts/test_week2.sh
    ./scripts/test_week2.sh
else
    echo -e "${RED}Error: scripts/test_week2.sh not found!${NC}"
    exit 1
fi

echo -e "\n${GREEN}=======================================${NC}"
echo -e "${GREEN}      ALL TEST SUITES PASSED!          ${NC}"
echo -e "${GREEN}=======================================${NC}"
