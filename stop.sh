#!/bin/bash
# 教员AI一键停止脚本 - stop.sh
# 用法: ./stop.sh
# 功能: 优雅停止后端、前端、清理资源

set -e

PROJECT_DIR="$HOME/jiaoyuan-ai-v2"
LOG_DIR="$PROJECT_DIR/logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[教员AI]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

log "正在停止教员AI服务..."

# 停止前端
log "停止前端..."
if [ -f "$LOG_DIR/frontend.pid" ]; then
    PID=$(cat "$LOG_DIR/frontend.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        sleep 1
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f "$LOG_DIR/frontend.pid"
fi
# 兜底：如果PID文件不存在，用pkill
if [ ! -f "$LOG_DIR/frontend.pid" ]; then
    pkill -f "vite.*--port 5173" 2>/dev/null || true
fi
ok "前端已停止"

# 停止后端
log "停止后端..."
if [ -f "$LOG_DIR/backend.pid" ]; then
    PID=$(cat "$LOG_DIR/backend.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f "$LOG_DIR/backend.pid"
fi
pkill -f "uvicorn.*api.main:app" 2>/dev/null || true
ok "后端已停止"

# 清理日志
log "清理日志..."
rm -f "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log" "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"
ok "日志已清理"

echo ""
echo "============================================"
echo -e "  ${GREEN}✅ 教员AI已完全停止${NC}"
echo "============================================"
