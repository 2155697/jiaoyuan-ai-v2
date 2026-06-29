#!/bin/bash
# 教员AI顾问 - 一键拉代码运行脚本（轻量版）
# 功能：拉取最新代码 → 停止旧进程 → 启动服务
# 适用：已配置好环境后的快速启动

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="qwen3:14b"
API_PORT=8000
FE_PORT=5173

echo "🚀 教员AI顾问 - 快速启动脚本"

# 1. 拉取最新代码
echo "📥 拉取 GitHub 最新代码..."
cd "$SCRIPT_DIR"
git fetch origin main

if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null; then
    echo "⚠️  检测到本地修改，丢弃并同步..."
    git reset --hard HEAD
fi

git checkout main 2>/dev/null || git checkout -b main
git reset --hard origin/main
git pull origin main
echo "✅ 代码已同步"

# 2. 停止旧进程
echo "🛑 停止旧进程..."
if [ -f "$SCRIPT_DIR/.backend.pid" ]; then
    OLD_PID=$(cat "$SCRIPT_DIR/.backend.pid" 2>/dev/null || echo "")
    [ -n "$OLD_PID" ] && kill "$OLD_PID" 2>/dev/null || true
    rm -f "$SCRIPT_DIR/.backend.pid"
fi

if [ -f "$SCRIPT_DIR/.frontend.pid" ]; then
    OLD_PID=$(cat "$SCRIPT_DIR/.frontend.pid" 2>/dev/null || echo "")
    [ -n "$OLD_PID" ] && kill "$OLD_PID" 2>/dev/null || true
    rm -f "$SCRIPT_DIR/.frontend.pid"
fi

pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
sleep 1
echo "✅ 旧进程已清理"

# 3. 检查 Ollama
echo "🔍 检查 Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama 未运行，请先启动：ollama serve"
    exit 1
fi

if ! curl -s http://localhost:11434/api/tags | grep -q "$MODEL"; then
    echo "⚠️  模型未下载，正在拉取 $MODEL..."
    ollama pull "$MODEL"
fi
echo "✅ Ollama 和模型已就绪"

# 4. 预热模型（可选，避免首次超时）
echo "🔥 预热模型..."
curl -s http://localhost:11434/api/generate \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"你好\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
    > /dev/null 2>&1 || echo "⚠️  预热失败，继续启动..."

# 5. 启动后端
echo "🔌 启动后端 (端口 $API_PORT)..."
cd "$SCRIPT_DIR"
source .venv/bin/activate 2>/dev/null || { echo "❌ 虚拟环境不存在，请先运行 ./jiaoyuan.sh"; exit 1; }

export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"
export OLLAMA_HOST="http://localhost:11434"
export MODEL_NAME="$MODEL"
export API_HOST="0.0.0.0"
export API_PORT="$API_PORT"
export LOG_LEVEL="INFO"
export ENABLE_THINKING="true"
export LLM_TIMEOUT="120"
export MAX_FULL_TURNS="10"
export CORS_ORIGINS="http://localhost:$FE_PORT,http://127.0.0.1:$FE_PORT"

mkdir -p logs
nohup python3 -m uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "$API_PORT" \
    --log-level warning \
    > logs/backend.log 2>&1 &

BACKEND_PID=$!
echo $BACKEND_PID > "$SCRIPT_DIR/.backend.pid"

# 等待后端启动
for i in {1..30}; do
    if curl -s http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
        echo "✅ 后端已就绪"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ 后端启动失败，查看日志："
        tail -n 30 "$SCRIPT_DIR/logs/backend.log"
        exit 1
    fi
    sleep 1
done

# 6. 启动前端
echo "🌐 启动前端 (端口 $FE_PORT)..."
cd "$SCRIPT_DIR/frontend"
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$SCRIPT_DIR/.frontend.pid"
sleep 2

if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ 前端启动失败"
    exit 1
fi
echo "✅ 前端已就绪"

# 7. 打印信息
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              🎉 服务启动成功！                          ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  🌐 前端: http://localhost:$FE_PORT                   ║"
echo "║  🔌 API:  http://localhost:$API_PORT/docs              ║"
echo "║  💓 健康: http://localhost:$API_PORT/api/health        ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  📋 日志: tail -f $SCRIPT_DIR/logs/backend.log        ║"
echo "║  ⏹️  停止: ./stop.sh                                   ║"
echo "╚════════════════════════════════════════════════════════╝"

# 保持运行
trap 'echo ""; echo "🛑 正在停止服务..."; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit 0' INT
wait
