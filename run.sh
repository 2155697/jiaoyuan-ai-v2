#!/bin/bash
# 教员AI顾问 - 一键启动（后端+前端+自动开浏览器）

cd ~/jiaoyuan-ai-v2
source .venv/bin/activate

echo "=========================================="
echo "  教员AI顾问 - 一键启动"
echo "=========================================="

# 1. 杀掉所有旧进程
echo "[1/5] 清理旧进程..."
pkill -f "start_server.py" 2>/dev/null
pkill -f "python.*http.server" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 2
echo "  ✓ 已清理"

# 2. 加载配置
echo "[2/5] 加载配置..."
set -a; source .env 2>/dev/null; set +a
export MODEL_NAME=${MODEL_NAME:-qwen3:8b}
echo "  ✓ 模型: $MODEL_NAME"

# 3. 检查Ollama
echo "[3/5] 检查Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  → 启动Ollama..."
    ollama serve &
    sleep 5
fi
echo "  ✓ Ollama正常"

# 4. 启动后端（后台）
echo "[4/5] 启动后端API..."
nohup python src/api/start_server.py > backend.log 2>&1 &
sleep 4
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  ✓ 后端: http://localhost:8000"
else
    echo "  ✗ 后端启动失败，看 backend.log"
    exit 1
fi

# 5. 启动前端 + 打开浏览器
echo "[5/5] 启动前端..."
cd frontend
nohup python3 -m http.server 5173 > frontend.log 2>&1 &
echo "  ✓ 前端: http://localhost:5173/simple.html"

echo ""
echo "=========================================="
echo "  全部启动成功！"
echo "=========================================="
echo ""
echo "  正在打开浏览器..."

# 等1秒确保server启动
sleep 1
open http://localhost:5173/simple.html

echo ""
echo "  后端日志: tail -f ~/jiaoyuan-ai-v2/backend.log"
echo "  停止命令: pkill -f start_server.py; pkill -f http.server"
echo ""
