#!/bin/bash
set -e

echo "========================================"
echo "  教员AI顾问 - 一键部署"
echo "========================================"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$PROJECT_DIR/src"
KNOWLEDGE_DIR="$PROJECT_DIR/knowledge"

# 0. 检查Python
echo "[1/6] 检查 Python3..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 请先安装 Python3 (brew install python)"
    exit 1
fi
echo "  Python3 已安装"

# 1. 创建目录
mkdir -p "$SRC_DIR" "$KNOWLEDGE_DIR"
echo "  目录结构就绪"

# 2. 创建虚拟环境
echo "[2/6] 创建虚拟环境..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
fi
source "$PROJECT_DIR/.venv/bin/activate"
echo "  虚拟环境已激活"

# 3. 安装依赖
echo "[3/6] 安装 Python 依赖..."
pip install -q PyMuPDF chromadb sentence-transformers gradio
echo "  依赖安装完成"

# 4. 检查Ollama
echo "[4/6] 检查 Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "  Ollama 未安装, 请手动安装: brew install --cask ollama"
    echo "  安装后运行: ollama serve"
    exit 1
fi
if ! pgrep -x "ollama" > /dev/null; then
    echo "  启动 Ollama 服务..."
    ollama serve &
    sleep 3
fi
echo "  Ollama 就绪"

# 5. 下载模型
echo "[5/6] 下载 AI 模型(约4GB, 需要一些时间)..."
if ollama list | grep -q "qwen2.5:7b"; then
    echo "  模型已存在"
else
    ollama pull qwen2.5:7b
    echo "  模型下载完成"
fi

# 6. 构建知识库
echo "[6/6] 构建知识库..."
cd "$PROJECT_DIR"
python3 "$SRC_DIR/extract_pdf.py"
python3 "$SRC_DIR/build_knowledge.py"

echo ""
echo "========================================"
echo "  部署完成!"
echo "========================================"
echo ""
echo "启动方式:"
echo "  cd $PROJECT_DIR"
echo "  ./start.sh"
echo ""
echo "浏览器打开: http://localhost:7860"
echo ""
