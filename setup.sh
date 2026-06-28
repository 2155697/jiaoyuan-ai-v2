#!/bin/bash
set -e

echo "========================================"
echo "  JiaoYuan AI - Setup"
echo "========================================"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check Python
echo "[1/5] Checking Python3..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Install: brew install python"
    exit 1
fi
echo "  OK"

# Create venv
echo "[2/5] Creating virtual environment..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
fi
source "$PROJECT_DIR/.venv/bin/activate"
echo "  OK"

# Install deps
echo "[3/5] Installing dependencies..."
pip install -q -r "$PROJECT_DIR/requirements.txt"
echo "  OK"

# Check Ollama
echo "[4/5] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama not found. Install: brew install --cask ollama"
    exit 1
fi
if ! pgrep -x "ollama" > /dev/null; then
    echo "  Starting Ollama..."
    ollama serve &
    sleep 3
fi
echo "  OK"

# Download model
echo "[5/5] Downloading AI model..."
if ollama list | grep -q "qwen2.5:7b"; then
    echo "  Model exists"
else
    ollama pull qwen2.5:7b
    echo "  Downloaded"
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  python3 src/build_knowledge.py"
echo "  ./start.sh"
echo ""
