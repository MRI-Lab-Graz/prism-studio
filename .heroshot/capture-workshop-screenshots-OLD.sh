#!/bin/bash

# PRISM Workshop - Heroshot Screenshot Capture Helper
# This script starts PRISM Studio and captures all workshop screenshots

set -e

echo "🎬 PRISM Workshop Heroshot Helper"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PRISM_URL="http://127.0.0.1:5001"
PRISM_PID=""
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Cleanup function
cleanup() {
    if [ -n "$PRISM_PID" ]; then
        echo ""
        echo -e "${YELLOW}Stopping PRISM Studio (PID: $PRISM_PID)...${NC}"
        kill $PRISM_PID 2>/dev/null || true
        sleep 2
    fi
}

# Set up trap to cleanup on exit
trap cleanup EXIT

# Check prerequisites
echo "🔍 Checking prerequisites..."
echo ""

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Install from: https://nodejs.org/${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Node.js $(node -v)"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} npm $(npm -v)"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $(python3 --version)"

echo ""

# Check if venv exists
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo -e "${RED}❌ Virtual environment not found at $PROJECT_ROOT/.venv${NC}"
    echo "Run: cd $PROJECT_ROOT && python3 -m venv .venv"
    exit 1
fi
echo -e "${GREEN}✓${NC} Virtual environment found"

echo ""
echo "📦 Installing Heroshot (if needed)..."
npm install -g heroshot@0.13.1 > /dev/null 2>&1 || npm install -g heroshot@0.13.1
echo -e "${GREEN}✓${NC} Heroshot ready"

echo ""
echo "🚀 Starting PRISM Studio..."
cd "$PROJECT_ROOT"
source .venv/bin/activate
python prism-studio.py > /tmp/prism-studio.log 2>&1 &
PRISM_PID=$!
echo "   PID: $PRISM_PID"
echo "   Log: /tmp/prism-studio.log"

# Wait for PRISM to start
echo ""
echo "⏳ Waiting for PRISM Studio to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s "$PRISM_URL/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PRISM Studio is ready at $PRISM_URL"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}❌ PRISM Studio failed to start after ${max_attempts}0 seconds${NC}"
    cat /tmp/prism-studio.log
    exit 1
fi

echo ""
echo "📸 Capturing screenshots..."
echo ""

cd "$SCRIPT_DIR"

# Check if config exists
if [ ! -f "config.json" ]; then
    echo -e "${RED}❌ config.json not found in $SCRIPT_DIR${NC}"
    exit 1
fi

# Run Heroshot
if npx heroshot --config config.json --clean; then
    echo ""
    echo -e "${GREEN}✓${NC} Screenshots captured successfully!"
    echo ""
    echo "📁 Screenshots saved to:"
    echo "   $PROJECT_ROOT/docs/_static/screenshots/"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Review screenshots: ls -la ../docs/_static/screenshots/"
    echo "   2. Commit changes: git add docs/_static/screenshots/"
    echo "   3. Commit with message: git commit -m 'chore(docs): update workshop screenshots'"
    echo ""
else
    echo -e "${RED}❌ Heroshot failed${NC}"
    exit 1
fi
