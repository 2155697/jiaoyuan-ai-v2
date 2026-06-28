#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

if ! pgrep -x "ollama" > /dev/null; then
    echo "启动Ollama..."
    ollama serve &
    sleep 3
fi

echo "启动教员AI顾问..."
echo "浏览器打开: http://localhost:7860"
cd "$PROJECT_DIR"
python3 "$PROJECT_DIR/src/chat_app.py"
