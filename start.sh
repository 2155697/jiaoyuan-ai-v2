#!/bin/bash
# 教员AI顾问 v3.0 - 启动脚本（精简版）
# 用法: ./start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "虚拟环境不存在，请先运行 ./setup.sh"
    exit 1
fi

source .venv/bin/activate

# 检查 Ollama
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "⚠ Ollama 未运行，正在启动..."
    ollama serve &
    sleep 3
fi

echo "✓ Ollama 运行中"

echo ""
echo "启动后端服务 (FastAPI)..."
echo "  API地址: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""

python src/api/start_server.py --host 0.0.0.0 --port 8000
