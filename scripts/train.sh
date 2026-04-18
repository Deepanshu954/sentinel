#!/bin/bash
# scripts/train.sh — Train ML Models

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}=== SENTINEL ML TRAINING ===${NC}\n"

# 1. Check Python 3.11+
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    echo -e "${RED}Python 3.11+ not found. Run scripts/build.sh first.${NC}"
    exit 1
fi

# 2. Check if models already exist
if [ -f "ml-service/model_weights/xgb_model.json" ]; then
    echo -e "${YELLOW}Models already trained.${NC}"
    if [ "${FORCE_RETRAIN:-0}" = "1" ]; then
        echo -e "${CYAN}FORCE_RETRAIN=1 set. Continuing with retraining.${NC}"
    elif [ -t 0 ]; then
        read -p "Retrain? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    else
        echo -e "${YELLOW}Non-interactive shell detected. Skipping retrain (set FORCE_RETRAIN=1 to override).${NC}"
        exit 0
    fi
fi

# 3. Directories
mkdir -p ml-service/data/raw ml-service/data/processed ml-service/model_weights

# 4. Optional public dataset fetch (for multi-source mode)
if [ "${USE_MULTISOURCE_DATA:-0}" = "1" ]; then
    if [ "${AUTO_FETCH_DATASETS:-1}" = "1" ]; then
        echo -e "${CYAN}Fetching open public datasets (NASA + Wikimedia)...${NC}"
        bash scripts/fetch_public_datasets.sh core || \
            echo -e "${YELLOW}Dataset fetch failed. Continuing; manifest fallback may apply.${NC}"
    else
        echo -e "${YELLOW}AUTO_FETCH_DATASETS=0, skipping dataset download.${NC}"
    fi
fi

# 5. Execute ML Pipeline — choose data source
echo -e "\n${CYAN}Processing Datasets...${NC}"

# Activate venv if available
if [ -f "/tmp/sentinel-venv/bin/activate" ]; then
    source /tmp/sentinel-venv/bin/activate
fi

if [ "${USE_MULTISOURCE_DATA:-0}" = "1" ]; then
    echo -e "${CYAN}Using multi-source pipeline (manifest-driven)...${NC}"
    python3 ml-service/scripts/build_multisource_training_data.py
else
    echo -e "${CYAN}Using legacy synthetic data pipeline...${NC}"
    python3 ml-service/scripts/prepare_dataset.py
fi

echo -e "\n${CYAN}Training XGBoost Predictors...${NC}"
python3 ml-service/ml/train_xgboost.py

echo -e "\n${CYAN}Training Isolation Forest...${NC}"
python3 ml-service/ml/train_isolation_forest.py

# 6. Verify outputs
echo -e "\n${CYAN}Verifying model geometry...${NC}"
if [ ! -f "ml-service/model_weights/xgb_model.json" ] || [ ! -f "ml-service/model_weights/isolation_forest.pkl" ]; then
    echo -e "${RED}ERROR: Expected model xgb_model.json or isolation_forest.pkl missing!${NC}"
    exit 1
fi

echo -e "\n${GREEN}${BOLD}Training complete. Models saved.${NC}"
echo -e "${YELLOW}${BOLD}IMPORTANT: Run docker-compose build ml-service to bake models into container${NC}"
echo -e "${BOLD}Then run ./launch.sh${NC}\n"
