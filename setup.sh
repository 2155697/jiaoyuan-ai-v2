#!/bin/bash
# 教员AI顾问 v3.0 - 一键部署脚本
# 支持: macOS (Apple Silicon / Intel)

set -e

echo "=========================================="
echo "  教员AI顾问 v3.0 - 一键部署"
echo "=========================================="
echo ""

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查命令
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# === 1. 检查Python ===
echo -e "${YELLOW}[1/7] 检查 Python 3.10+...${NC}"
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  Python版本: $PYTHON_VERSION"
else
    echo -e "${RED}错误: 未找到 python3${NC}"
    echo "请安装 Python 3.10+: https://www.python.org/downloads/"
    exit 1
fi

# === 2. 检查Ollama ===
echo -e "${YELLOW}[2/7] 检查 Ollama...${NC}"
if command_exists ollama; then
    echo -e "${GREEN}  Ollama 已安装${NC}"
    ollama --version 2>/dev/null || true
else
    echo "  Ollama 未安装，正在安装..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "${GREEN}  Ollama 安装完成${NC}"
fi

# === 3. 拉取Qwen3:8b模型 ===
echo -e "${YELLOW}[3/7] 检查 Qwen3:8b 模型...${NC}"
if ollama list 2>/dev/null | grep -q "qwen3"; then
    echo -e "${GREEN}  Qwen3 模型已存在${NC}"
else
    echo "  正在拉取 Qwen3:8b（约5GB，请耐心等待）..."
    ollama pull qwen3:8b
    echo -e "${GREEN}  Qwen3:8b 拉取完成${NC}"
fi

# === 4. 创建虚拟环境 ===
echo -e "${YELLOW}[4/7] 创建虚拟环境...${NC}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}  虚拟环境创建完成${NC}"
else
    echo "  虚拟环境已存在"
fi

# === 5. 安装依赖 ===
echo -e "${YELLOW}[5/7] 安装 Python 依赖...${NC}"
source .venv/bin/activate
pip install --upgrade pip

# 使用清华镜像加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo -e "${GREEN}  依赖安装完成${NC}"

# === 6. 构建知识库 ===
echo -e "${YELLOW}[6/7] 构建认知知识库...${NC}"
python3 -c "
import sys
sys.path.insert(0, 'src')
from core.cognitive_graph import CognitiveGraph
from core.maoxuan_retriever import MaoxuanRetriever
import os

print('  初始化认知图谱...')
graph = CognitiveGraph()
graph.load_builtin_data()
print(f'  图谱加载完成: {len(graph.graph.nodes)} 节点, {len(graph.graph.edges)} 边')

print('  初始化毛选检索器...')
retriever = MaoxuanRetriever()
print(f'  毛选检索器就绪')
print('  知识库构建完成')
"

# === 7. 构建前端 ===
echo -e "${YELLOW}[7/7] 构建前端...${NC}"
if [ -d "frontend" ]; then
    cd frontend
    if command_exists npm; then
        echo "  安装前端依赖..."
        npm install
        echo "  构建前端..."
        npm run build
        echo -e "${GREEN}  前端构建完成${NC}"
    else
        echo -e "${YELLOW}  警告: 未找到 npm，跳过前端构建${NC}"
        echo "  如需前端界面，请安装 Node.js: https://nodejs.org/"
    fi
    cd "$PROJECT_DIR"
else
    echo "  前端目录不存在，跳过"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=========================================="
echo ""
echo "启动命令:"
echo "  ./start.sh"
echo ""
echo "或分别启动:"
echo "  终端1: ollama serve"
echo "  终端2: source .venv/bin/activate && python src/api/start_server.py"
echo "  终端3: cd frontend && npm run dev（如需前端开发服务器）"
echo ""
echo "前端访问: http://localhost:5173"
echo "API文档:  http://localhost:8000/docs"
echo ""
