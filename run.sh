#!/bin/bash
# 教员AI一键启动脚本 - run.sh
# 用法: ./run.sh
# 功能: 拉取最新代码 → 修复配置 → 启动所有服务 → 打开浏览器

set -e

PROJECT_DIR="$HOME/jiaoyuan-ai-v2"
LOG_DIR="$PROJECT_DIR/logs"
VENV="$PROJECT_DIR/.venv/bin/activate"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[教员AI]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

# ========== 1. 进入项目目录 ==========
log "进入项目目录..."
cd "$PROJECT_DIR" || { err "项目目录不存在: $PROJECT_DIR"; exit 1; }

# ========== 2. 拉取最新代码 ==========
log "拉取 GitHub 最新代码..."
git fetch origin main
git reset --hard origin/main
ok "代码已更新到最新"

# ========== 3. 修复 .env 模型配置 ==========
log "检查模型配置..."
if grep -q "MODEL_NAME=qwen3:30b-a3b" .env 2>/dev/null; then
    sed -i '' 's/^MODEL_NAME=.*/MODEL_NAME=qwen3:14b/' .env
    ok ".env 模型已修正为 qwen3:14b（适配24GB Mac）"
else
    ok ".env 模型配置正常"
fi

# ========== 4. 确保虚拟环境存在 ==========
log "检查 Python 虚拟环境..."
if [ ! -f "$VENV" ]; then
    warn "虚拟环境不存在，正在创建..."
    python3 -m venv .venv
    source "$VENV"
    pip install --upgrade pip
    pip install -r requirements.txt
    ok "虚拟环境创建完成"
else
    source "$VENV"
    ok "虚拟环境已激活"
fi

# ========== 5. 清理旧进程 ==========
log "清理旧进程..."
pkill -f "uvicorn.*api.main:app" 2>/dev/null || true
pkill -f "vite.*--port 5173" 2>/dev/null || true
sleep 2
ok "旧进程已清理"

# ========== 6. 检查 Ollama ==========
log "检查 Ollama 服务..."
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    warn "Ollama 未启动，正在启动..."
    open -a Ollama
    sleep 5
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            ok "Ollama 已启动"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            err "Ollama 启动超时，请手动启动 Ollama.app"
            exit 1
        fi
    done
else
    ok "Ollama 已在运行"
fi

# ========== 7. 预加载模型 ==========
log "预加载 qwen3:14b 模型到内存..."
MODEL_READY=$(curl -s http://localhost:11434/api/ps 2>/dev/null | grep -c "qwen3:14b" || true)
if [ "$MODEL_READY" -gt 0 ]; then
    ok "模型已在内存中"
else
    ( curl -s http://localhost:11434/api/generate \
        -d '{"model":"qwen3:14b","prompt":"你好","stream":false,"options":{"num_predict":1}}' \
        >/dev/null 2>&1 ) &
    for i in {1..60}; do
        sleep 2
        if curl -s http://localhost:11434/api/ps 2>/dev/null | grep -q "qwen3:14b"; then
            ok "模型已加载到内存"
            break
        fi
        if [ $i -eq 60 ]; then
            warn "模型预热可能未完成，继续启动..."
        fi
    done
fi

# ========== 8. 启动后端（nohup + disown 确保独立） ==========
log "启动后端服务 (端口 $BACKEND_PORT)..."
mkdir -p "$LOG_DIR"
export PYTHONPATH="$PROJECT_DIR/src"
export MODEL_NAME="qwen3:14b"
export API_PORT="$BACKEND_PORT"

(
    cd "$PROJECT_DIR"
    source "$VENV"
    export PYTHONPATH="$PROJECT_DIR/src"
    nohup python3 -m uvicorn api.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --log-level warning \
        > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOG_DIR/backend.pid"
    disown
) &

for i in {1..30}; do
    sleep 1
    if curl -s http://localhost:$BACKEND_PORT/api/health >/dev/null 2>&1; then
        ok "后端已就绪 (http://localhost:$BACKEND_PORT)"
        break
    fi
    if [ $i -eq 30 ]; then
        err "后端启动超时，请检查日志: $LOG_DIR/backend.log"
        exit 1
    fi
done

# ========== 9. 启动前端 ==========
log "启动前端服务 (端口 $FRONTEND_PORT)..."
(
    cd "$PROJECT_DIR/frontend"
    nohup node node_modules/.bin/vite \
        --host \
        --port "$FRONTEND_PORT" \
        > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$LOG_DIR/frontend.pid"
    disown
) &

for i in {1..20}; do
    sleep 1
    if curl -s http://localhost:$FRONTEND_PORT >/dev/null 2>&1; then
        ok "前端已就绪 (http://localhost:$FRONTEND_PORT)"
        break
    fi
    if [ $i -eq 20 ]; then
        err "前端启动超时，请检查日志: $LOG_DIR/frontend.log"
        exit 1
    fi
done

# ========== 10. 打开浏览器 ==========
log "打开浏览器..."
sleep 2
open "http://localhost:$FRONTEND_PORT"
ok "浏览器已打开"

# ========== 11. 完成提示 ==========
echo ""
echo "============================================"
echo -e "  ${GREEN}🎉 教员AI已启动完成！${NC}"
echo "============================================"
echo ""
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  API文档: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "  模型: qwen3:14b (适配你的24GB Mac)"
echo "  日志: $LOG_DIR/"
echo ""
echo "  使用: 在浏览器输入框提问，观察进度条回复"
echo ""
echo "  停止: ./stop.sh"
echo "============================================"
