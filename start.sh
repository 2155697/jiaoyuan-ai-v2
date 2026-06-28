#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

echo "Starting JiaoYuan AI Advisor..."
echo "Open: http://localhost:7861"
echo ""

cd "$PROJECT_DIR"
python3 "$PROJECT_DIR/src/chat_app.py"
