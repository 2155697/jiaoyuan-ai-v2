#!/bin/bash
# 教员AI顾问 - 停止服务脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

stop_process() {
    local name="$1"
    local pid_file="$2"
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            log_info "${name} 已停止 (PID: ${PID})"
        else
            log_warn "${name} 进程 ${PID} 不存在"
        fi
        rm -f "$pid_file"
    else
        log_warn "未找到 ${name} 的 PID 文件"
    fi
}

stop_process "后端" "$SCRIPT_DIR/.backend.pid"
stop_process "前端" "$SCRIPT_DIR/.frontend.pid"

log_info "所有服务已停止"
