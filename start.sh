#!/bin/bash
# 教员AI顾问 v3.0 - 启动脚本

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  教员AI顾问 v3.0${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "虚拟环境不存在，请先运行 ./setup.sh"
    exit 1
fi

source .venv/bin/activate

# 检查Ollama
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Ollama 未运行，正在启动...${NC}"
    ollama serve &
    sleep 3
fi

echo -e "${GREEN}✓ Ollama 运行中${NC}"

# 启动后端
echo ""
echo -e "${YELLOW}启动后端服务 (FastAPI)...${NC}"
echo "  API地址: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""

python src/api/start_server.py --host 0.0.0.0 --port 8000
