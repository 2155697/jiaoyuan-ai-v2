#!/bin/bash
# 教员AI顾问 v3.0 - 一键修复+启动脚本
# 针对MacBook M5 24GB

cd ~/jiaoyuan-ai-v2
source .venv/bin/activate

echo "=========================================="
echo "  教员AI顾问 - 修复 + 启动"
echo "=========================================="

# ===== 第1步：修复 dependencies.py 的导入 =====
echo "[1/5] 修复代码导入问题..."
if ! grep -q "from fastapi import Depends" src/api/dependencies.py; then
    sed -i '' '16i\
from fastapi import Depends\
' src/api/dependencies.py
    echo "  ✓ 已修复 dependencies.py"
else
    echo "  ✓ dependencies.py 已正确"
fi

# ===== 第2步：加载环境变量 =====
echo "[2/5] 加载环境变量..."
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "  ✓ MODEL_NAME=$MODEL_NAME"
else
    echo "  ⚠ .env 不存在，使用默认 qwen3:8b"
    export MODEL_NAME=qwen3:8b
fi

# ===== 第3步：确保依赖完整 =====
echo "[3/5] 检查依赖..."
pip install fastapi uvicorn websockets aiohttp pydantic python-dotenv \
    networkx chromadb sentence-transformers torch numpy \
    httpx structlog python-multipart \
    -i https://pypi.tuna.tsinghua.edu.cn/simple -q 2>/dev/null
echo "  ✓ 依赖已就绪"

# ===== 第4步：验证 Ollama =====
echo "[4/5] 检查 Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  ✓ Ollama 运行中"
else
    echo "  ✗ Ollama 未运行！请先开新终端执行: ollama serve"
    exit 1
fi

# ===== 第5步：启动服务器 =====
echo "[5/5] 启动 API 服务器..."
echo "=========================================="
echo "  浏览器打开: http://localhost:5173"
echo "  API 文档:   http://localhost:8000/docs"
echo "=========================================="
python src/api/start_server.py
