#!/bin/bash
# scripts/build.sh — One-time Mac setup

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}=== SENTINEL BUILD SETTING UP ENVIRONMENT ===${NC}\n"

INSTALLED=()
PRESENT=()

check_cmd() { command -v "$1" >/dev/null 2>&1; }

# 1. Homebrew
if ! check_cmd brew; then
    echo -e "${YELLOW}Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || exit 1
    INSTALLED+=("Homebrew")
else
    PRESENT+=("Homebrew")
fi

# 2. Go
if ! check_cmd go; then
    echo -e "${YELLOW}Installing Go...${NC}"
    brew install go || exit 1
    INSTALLED+=("Go")
else
    PRESENT+=("Go")
fi

# 3. Java 21
if ! /usr/libexec/java_home -v 21 >/dev/null 2>&1; then
    echo -e "${YELLOW}Installing Java 21 (Temurin)...${NC}"
    brew install --cask temurin@21 || exit 1
    INSTALLED+=("Java 21")
else
    PRESENT+=("Java 21")
fi

# 4. Python 3.11+
if ! check_cmd python3.11 && ! python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    echo -e "${YELLOW}Installing Python 3.11...${NC}"
    brew install python@3.11 || exit 1
    INSTALLED+=("Python 3.11")
else
    PRESENT+=("Python 3.11+")
fi

# 5. Maven
if ! check_cmd mvn; then
    echo -e "${YELLOW}Installing Maven...${NC}"
    brew install maven || exit 1
    INSTALLED+=("Maven")
else
    PRESENT+=("Maven")
fi

# 6. hey
if ! check_cmd hey; then
    echo -e "${YELLOW}Installing hey...${NC}"
    brew install hey || exit 1
    INSTALLED+=("hey")
else
    PRESENT+=("hey")
fi

# 7. Python Packages
echo -e "${CYAN}Checking Python dependencies...${NC}"
python3 -m venv /tmp/sentinel-venv
source /tmp/sentinel-venv/bin/activate
pip install --quiet xgboost scikit-learn pandas numpy fastapi uvicorn pydantic pyarrow PyJWT requests || exit 1
INSTALLED+=("Python ML Packages (venv)")

# 8. Docker
if ! check_cmd docker || ! docker info >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker Desktop is not running or not installed.${NC}"
    echo -e "Please download and install from: ${BOLD}https://www.docker.com/products/docker-desktop/${NC}"
    exit 1
else
    PRESENT+=("Docker Desktop (Running)")
fi

# 9. Environment File
if [ ! -f .env ] && [ -f .env.example ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
    INSTALLED+=(".env created")
else
    PRESENT+=(".env exists")
fi

# Summary
echo -e "\n${GREEN}${BOLD}=== Setup Summary ===${NC}"
echo -e "${CYAN}Already present:${NC} ${PRESENT[*]}"
if [ ${#INSTALLED[@]} -gt 0 ]; then
    echo -e "${GREEN}Installed just now:${NC} ${INSTALLED[*]}"
fi

echo -e "\n${BOLD}${GREEN}Setup complete. Next: run scripts/train.sh${NC}\n"
