#!/bin/bash
# 教员AI顾问 v3.0 - 一键部署脚本（精简版）
# 支持: macOS / Linux

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  教员AI顾问 v3.0 - 一键部署"
echo "=========================================="
echo ""

command_exists() { command -v "$1" >/dev/null 2>&1; }

# 1. 检查 Python
echo "[1/5] 检查 Python 3.10+..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  Python版本: $PYTHON_VERSION"
else
    echo "错误: 未找到 python3"
    exit 1
fi

# 2. 检查 Ollama
echo "[2/5] 检查 Ollama..."
if command_exists ollama; then
    echo "  Ollama 已安装"
    ollama --version 2>/dev/null || true
else
    echo "  Ollama 未安装，正在安装..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "  Ollama 安装完成"
fi

# 3. 拉取模型
echo "[3/5] 检查 Qwen3 模型..."
if ollama list 2>/dev/null | grep -q "qwen3"; then
    echo "  Qwen3 模型已存在"
else
    echo "  正在拉取 Qwen3:8b（约5GB，请耐心等待）..."
    ollama pull qwen3:8b
    echo "  Qwen3:8b 拉取完成"
fi

# 4. 创建虚拟环境并安装依赖
echo "[4/5] 安装 Python 依赖..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  虚拟环境创建完成"
else
    echo "  虚拟环境已存在"
fi

source .venv/bin/activate
pip install --upgrade pip

# 使用清华镜像加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "  依赖安装完成"

# 5. 构建知识库
echo "[5/5] 构建认知知识库..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from core.cognitive_graph import CognitiveGraph
from core.maoxuan_retriever import MaoxuanRetriever

print('  初始化认知图谱...')
graph = CognitiveGraph()
graph.load_builtin_data()
print(f'  图谱加载完成: {len(graph.graph.nodes)} 节点, {len(graph.graph.edges)} 边')

print('  初始化毛选检索器...')
retriever = MaoxuanRetriever()
retriever.build_index()
print(f'  毛选检索器就绪: {retriever.get_stats()[\"document_count\"]} 文档')
print('  知识库构建完成')
"

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "启动命令:"
echo "  ./start.sh"
echo ""
echo "API文档:  http://localhost:8000/docs"
echo "前端访问: 打开 frontend/simple.html 或 cd frontend && npm run dev"
echo ""
