#!/bin/bash
# =============================================================
# Entri POC — One-time Setup Script
# Run from the project root: bash setup.sh
# =============================================================

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
DATA_DIR="$BACKEND_DIR/data"
VENV_DIR="$ROOT_DIR/.venv"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

ok()   { echo -e "${GREEN}  ✓ $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $1${NC}"; }
fail() { echo -e "${RED}  ✗ $1${NC}"; }
step() { echo -e "\n${YELLOW}▶ $1${NC}"; }

echo ""
echo "============================================"
echo "         Entri POC — Setup & Check"
echo "============================================"

# -----------------------------------------------------------
# 1. System dependencies (macOS / Homebrew)
# -----------------------------------------------------------
step "Checking system dependencies..."

if ! command -v brew &>/dev/null; then
    fail "Homebrew not found. Install it from https://brew.sh and re-run."
    exit 1
fi
ok "Homebrew found"

MISSING_BREW=()
for pkg in tesseract cmake; do
    if brew list "$pkg" &>/dev/null; then
        ok "$pkg installed"
    else
        MISSING_BREW+=("$pkg")
        warn "$pkg not installed"
    fi
done

if [ ${#MISSING_BREW[@]} -gt 0 ]; then
    echo ""
    echo "Installing missing brew packages: ${MISSING_BREW[*]}"
    brew install "${MISSING_BREW[@]}"
    ok "Installed ${MISSING_BREW[*]}"
fi

# -----------------------------------------------------------
# 2. Python 3.11
# -----------------------------------------------------------
step "Checking Python 3.11..."

if command -v python3.11 &>/dev/null; then
    ok "python3.11 found: $(python3.11 --version)"
    PYTHON=python3.11
elif command -v python3 &>/dev/null && python3 --version 2>&1 | grep -q "3\.11"; then
    ok "python3 is 3.11: $(python3 --version)"
    PYTHON=python3
else
    fail "Python 3.11 not found. Install via: brew install python@3.11"
    exit 1
fi

# -----------------------------------------------------------
# 3. Virtual environment
# -----------------------------------------------------------
step "Setting up virtual environment..."

if [ -d "$VENV_DIR" ]; then
    ok "Virtual environment already exists at .venv/"
else
    $PYTHON -m venv "$VENV_DIR"
    ok "Created virtual environment at .venv/"
fi

# Activate venv for the rest of the script
source "$VENV_DIR/bin/activate"

# -----------------------------------------------------------
# 4. Python dependencies
# -----------------------------------------------------------
step "Installing Python dependencies..."

if [ -f "$BACKEND_DIR/requirements.txt" ]; then
    pip install --quiet --upgrade pip
    pip install --quiet -r "$BACKEND_DIR/requirements.txt"
    ok "Dependencies installed from requirements.txt"
else
    warn "requirements.txt not found at backend/requirements.txt — skipping pip install"
fi

# -----------------------------------------------------------
# 5. Create required directories
# -----------------------------------------------------------
step "Creating required directories..."

for dir in \
    "$DATA_DIR" \
    "$BACKEND_DIR/faces" \
    "$BACKEND_DIR/live_faces" \
    "$BACKEND_DIR/tickets" \
    "$BACKEND_DIR/uploads"; do
    mkdir -p "$dir"
    ok "$(realpath --relative-to="$ROOT_DIR" "$dir")/"
done

# -----------------------------------------------------------
# 6. Create missing JSON data files
# -----------------------------------------------------------
step "Checking JSON data files in backend/data/..."

# Files that should contain an empty array []
ARRAY_FILES=("users.json" "organizers.json" "events.json" "tickets.json")
# Files that should contain an empty object {}
OBJECT_FILES=("attendance.json")

for f in "${ARRAY_FILES[@]}"; do
    FILE="$DATA_DIR/$f"
    if [ -f "$FILE" ]; then
        ok "$f already exists"
    else
        echo "[]" > "$FILE"
        ok "$f created (empty array)"
    fi
done

for f in "${OBJECT_FILES[@]}"; do
    FILE="$DATA_DIR/$f"
    if [ -f "$FILE" ]; then
        ok "$f already exists"
    else
        echo "{}" > "$FILE"
        ok "$f created (empty object)"
    fi
done

# -----------------------------------------------------------
# 7. Final health check
# -----------------------------------------------------------
step "Running health check..."

ALL_OK=true

REQUIRED_FILES=(
    "backend/main.py"
    "backend/storage.py"
    "backend/organizers.py"
    "backend/blockchain.py"
    "backend/data/users.json"
    "backend/data/organizers.json"
    "backend/data/events.json"
    "backend/data/tickets.json"
    "backend/data/attendance.json"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$ROOT_DIR/$f" ]; then
        ok "$f"
    else
        fail "$f MISSING"
        ALL_OK=false
    fi
done

REQUIRED_DIRS=(
    "backend/data"
    "backend/faces"
    "backend/live_faces"
    "backend/tickets"
    "backend/uploads"
    "frontend"
)

for d in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$ROOT_DIR/$d" ]; then
        ok "$d/"
    else
        fail "$d/ MISSING"
        ALL_OK=false
    fi
done

# -----------------------------------------------------------
# Done
# -----------------------------------------------------------
echo ""
echo "============================================"
if $ALL_OK; then
    echo -e "${GREEN}  All checks passed! Ready to run.${NC}"
    echo ""
    echo "  To start the server:"
    echo "    source .venv/bin/activate"
    echo "    cd backend"
    echo "    uvicorn main:app --reload"
else
    echo -e "${RED}  Some checks failed. Fix the issues above and re-run.${NC}"
fi
echo "============================================"
echo ""
