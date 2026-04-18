#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Auto-detect docker compose command (modern plugin first, then legacy)
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Neither 'docker compose' nor 'docker-compose' found.${NC}"
    exit 1
fi

case $1 in

  start)
    ./launch.sh
    ;;

  stop)
    echo -e "${YELLOW}Stopping Sentinel...${NC}"
    $COMPOSE_CMD --env-file /dev/null down
    echo -e "${GREEN}Done.${NC}"
    ;;

  restart)
    $COMPOSE_CMD --env-file /dev/null down
    sleep 2
    $COMPOSE_CMD --env-file /dev/null up -d
    sleep 10
    $COMPOSE_CMD --env-file /dev/null ps
    ;;

  status)
    $COMPOSE_CMD --env-file /dev/null ps
    ;;

  logs)
    SERVICE=${2:-orchestrator}
    $COMPOSE_CMD --env-file /dev/null logs -f $SERVICE
    ;;

  token)
    TOKEN=$(python3 scripts/generate_jwt.py)
    echo -e "${GREEN}Token:${NC}"
    echo $TOKEN
    echo ""
    echo -e "${BLUE}Copy this curl command:${NC}"
    echo curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test
    ;;

  curl)
    TOKEN=$(python3 scripts/generate_jwt.py)
    echo -e "${BLUE}Response:${NC}"
    curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test
    echo ""
    ;;

  test)
    bash scripts/validate_sentinel.sh
    ;;

  demo)
    bash scripts/demo.sh
    ;;

  datasets)
    bash scripts/fetch_public_datasets.sh core
    ;;

  influx)
    echo -e "${BLUE}Resetting InfluxDB password...${NC}"
    $COMPOSE_CMD --env-file /dev/null exec influxdb influx user password \
      --name admin \
      --password sentinel123 \
      --token sentinel-influx-admin-token
    echo -e "${GREEN}Done. Login with: admin / sentinel123${NC}"
    ;;

  build)
    SERVICE=${2:-orchestrator}
    echo -e "${BLUE}Building $SERVICE...${NC}"
    $COMPOSE_CMD --env-file /dev/null build $SERVICE
    $COMPOSE_CMD --env-file /dev/null up -d $SERVICE
    echo -e "${GREEN}Done.${NC}"
    ;;

  clean)
    echo -e "${RED}This deletes ALL data. Type yes to confirm:${NC}"
    read confirm
    if [ "$confirm" = "yes" ]; then
      $COMPOSE_CMD --env-file /dev/null down -v
      echo -e "${GREEN}Cleaned. Run ./launch.sh to start fresh.${NC}"
    else
      echo "Cancelled."
    fi
    ;;

  help|*)
    echo -e "${BLUE}Sentinel Commands:${NC}"
    echo "  ./sentinel.sh start        - start everything"
    echo "  ./sentinel.sh stop         - stop everything"
    echo "  ./sentinel.sh restart      - restart everything"
    echo "  ./sentinel.sh status       - show running services"
    echo "  ./sentinel.sh logs         - orchestrator logs"
    echo "  ./sentinel.sh logs gateway - specific service logs"
    echo "  ./sentinel.sh token        - generate JWT token"
    echo "  ./sentinel.sh curl         - fire a live test request"
    echo "  ./sentinel.sh test         - run 30-point validation"
    echo "  ./sentinel.sh demo         - run live demo"
    echo "  ./sentinel.sh datasets     - download local public datasets"
    echo "  ./sentinel.sh influx       - reset InfluxDB password"
    echo "  ./sentinel.sh build        - rebuild a service"
    echo "  ./sentinel.sh clean        - delete all data"
    ;;

esac
