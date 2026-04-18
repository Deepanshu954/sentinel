#!/bin/bash
# scripts/fetch_public_datasets.sh
# Download local-friendly public datasets for Sentinel training.

set -euo pipefail

RAW_DIR="${RAW_DIR:-ml-service/data/raw}"
MODE="${1:-core}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$RAW_DIR"

download() {
    local url="$1"
    local out="$2"
    if [ -f "$out" ]; then
        echo -e "  ${YELLOW}SKIP${NC} $out (already exists)"
        return 0
    fi

    echo -e "  ${CYAN}GET${NC}  $url"
    curl --fail --location --retry 3 --connect-timeout 15 "$url" -o "$out"
    echo -e "  ${GREEN}OK${NC}   $out"
}

echo -e "${CYAN}Fetching public datasets into ${RAW_DIR}${NC}"

# 1) NASA HTTP logs (classic, high-volume web traffic)
download "https://ita.ee.lbl.gov/traces/NASA_access_log_Jul95.gz" "$RAW_DIR/NASA_access_log_Jul95.gz"
download "https://ita.ee.lbl.gov/traces/NASA_access_log_Aug95.gz" "$RAW_DIR/NASA_access_log_Aug95.gz"

# 2) Wikimedia hourly pageviews snapshot (modern demand signal)
download "https://dumps.wikimedia.org/other/pageviews/2024/2024-01/pageviews-20240101-000000.gz" \
    "$RAW_DIR/pageviews-20240101-000000.gz"

if [ "$MODE" = "extended" ]; then
    # Optional: another hour to extend local series quickly
    download "https://dumps.wikimedia.org/other/pageviews/2024/2024-01/pageviews-20240101-010000.gz" \
        "$RAW_DIR/pageviews-20240101-010000.gz"
fi

echo -e "\n${GREEN}Dataset fetch complete.${NC}"
echo "Suggested next step:"
echo "  USE_MULTISOURCE_DATA=1 bash scripts/train.sh"
