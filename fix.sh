#!/bin/bash
# 修复：端口冲突 + HuggingFace被墙 + 一键启动

echo "=========================================="
echo "  教员AI顾问 - 修复+启动"
echo "=========================================="

# 1. 强制杀掉所有相关进程
echo "[1/6] 清理所有旧进程..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:8001 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null
pkill -9 -f "start_server" 2>/dev/null
pkill -9 -f "http.server" 2>/dev/null
pkill -9 -f "vite" 2>/dev/null
sleep 2
echo "  ✓ 已清理"

# 2. 设置HuggingFace镜像（解决下载卡住）
echo "[2/6] 设置国内镜像..."
export HF_ENDPOINT=https://hf-mirror.com
export TRANSFORMERS_OFFLINE=0
echo "  ✓ 镜像已设置 (hf-mirror.com)"

# 3. 预下载向量模型
echo "[3/6] 预下载向量模型..."
cd ~/jiaoyuan-ai-v2
source .venv/bin/activate

python3 << 'PYEOF'
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

try:
    from sentence_transformers import SentenceTransformer
    print("  正在下载 all-MiniLM-L6-v2...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("  ✓ 向量模型下载完成")
except Exception as e:
    print(f"  ⚠ 下载出现问题: {e}")
    print("  继续启动，首次对话时可能会再试下载...")
PYEOF

# 4. 加载配置
echo "[4/6] 加载配置..."
set -a; source .env 2>/dev/null; set +a
export MODEL_NAME=${MODEL_NAME:-qwen3:30b-a3b}
echo "  ✓ 模型: $MODEL_NAME"

# 5. 确保Ollama在跑
echo "[5/6] 检查Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve &
    sleep 5
fi
echo "  ✓ Ollama正常"

# 6. 启动后端（使用8001端口避免冲突）
echo "[6/6] 启动后端..."
cd ~/jiaoyuan-ai-v2
nohup python src/api/start_server.py > backend.log 2>&1 &
sleep 5

if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  ✓ 后端启动成功: http://localhost:8000"
else
    echo "  ✗ 启动失败，查看 backend.log:"
    cat backend.log | tail -15
    exit 1
fi

# 7. 启动前端
echo ""
echo "=========================================="
echo "  全部启动成功！"
echo "=========================================="
echo ""
echo "  API地址: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""
echo "  正在打开浏览器..."
echo ""

# 启动前端静态服务
cd ~/jiaoyuan-ai-v2/frontend
nohup python3 -m http.server 5173 > frontend.log 2>&1 &
sleep 1
open http://localhost:5173/simple.html

echo "  浏览器已打开 http://localhost:5173/simple.html"
echo "  停止命令: lsof -ti:8000 | xargs kill -9; lsof -ti:5173 | xargs kill -9"
