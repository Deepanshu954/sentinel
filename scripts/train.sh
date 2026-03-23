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
if [ -f "ml-service/models/xgb_model.json" ]; then
    echo -e "${YELLOW}Models already trained.${NC}"
    read -p "Retrain? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# 3. Directories
mkdir -p ml-service/data/raw ml-service/data/processed ml-service/models

# 4. Check & Download Datasets
WIKI_FILE="ml-service/data/raw/wiki_traffic.csv"
AZURE_FILE="ml-service/data/raw/azure_traces.csv"

if [ ! -f "$WIKI_FILE" ]; then
    echo -e "${YELLOW}Missing real datasets.${NC}"
    echo -e "DATASET 1: Wikipedia Web Traffic (Kaggle)"
    echo -e "Download from: ${BOLD}https://www.kaggle.com/datasets/cpmpml/web-traffic-time-series-forecasting${NC}"
    echo -e "Place train_1.csv at ${BOLD}${WIKI_FILE}${NC}"
    
    echo -e "\nDATASET 2: Azure Traces will be downloaded automatically..."
    curl -sL https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/AzurePublicDatasetV1.csv -o "$AZURE_FILE"
    
    if [ ! -f "$WIKI_FILE" ]; then
        echo -e "\n${RED}${BOLD}WARNING: Using synthetic fallback data${NC} since ${WIKI_FILE} is still missing."
    fi
else
    # If wiki exists, still ensure azure exists
    if [ ! -f "$AZURE_FILE" ]; then
        echo -e "${CYAN}Downloading Azure Traces...${NC}"
        curl -sL https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/AzurePublicDatasetV1.csv -o "$AZURE_FILE"
    fi
fi

# 5. Execute ML Pipeline
echo -e "\n${CYAN}Processing Datasets...${NC}"
source /tmp/sentinel-venv/bin/activate

python3 ml-service/scripts/prepare_dataset.py

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
