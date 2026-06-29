#!/bin/bash
set -e

# =============================================================================
# 一键启动脚本：同时启动后端(FastAPI)和前端(Vite)
# 适用环境：macOS M5, Python 3.14, Node.js/npm
# 项目路径：~/jiaoyuan-ai-v2
# =============================================================================

# ---------------------------------------------------------------------------
# 颜色定义
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ---------------------------------------------------------------------------
# 日志函数
# ---------------------------------------------------------------------------
log() {
    echo -e "${BLUE}[INFO]${NC}  $1"
}

ok() {
    echo -e "${GREEN}[OK]${NC}   $1"
}

err() {
    echo -e "${RED}[ERR]${NC}  $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

step() {
    echo -e ""
    echo -e "${BOLD}${MAGENTA}==>${NC} ${BOLD}$1${NC}"
}

# ---------------------------------------------------------------------------
# 项目目录检测
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"

step "检测项目目录"
log "项目目录: ${PROJECT_DIR}"

# 检查关键文件/目录是否存在
if [[ ! -d "${PROJECT_DIR}/src" ]]; then
    err "未找到 src/ 目录，请在项目根目录下执行此脚本"
    exit 1
fi

if [[ ! -d "${PROJECT_DIR}/frontend" ]]; then
    err "未找到 frontend/ 目录"
    exit 1
fi

ok "项目目录验证通过"

# ---------------------------------------------------------------------------
# 日志目录创建
# ---------------------------------------------------------------------------
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"

# 清空旧日志
> "${BACKEND_LOG}"
> "${FRONTEND_LOG}"
ok "日志目录准备就绪: ${LOG_DIR}"

# ---------------------------------------------------------------------------
# 端口检查函数
# ---------------------------------------------------------------------------
check_port() {
    local port=$1
    local service=$2

    if lsof -Pi ":${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pid
        pid=$(lsof -Pi ":${port}" -sTCP:LISTEN -t 2>/dev/null | head -n1)
        err "端口 ${port} 已被占用 (PID: ${pid}) — ${service}"
        err "请先执行 stop.sh 停止现有服务，或手动释放端口"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 后端启动函数
# ---------------------------------------------------------------------------
start_backend() {
    step "启动后端服务 (FastAPI)"

    # 端口冲突检查
    check_port 8000 "FastAPI"

    # 检查 Python/uvicorn 是否可用
    if ! command -v uvicorn &>/dev/null; then
        if command -v python3 &>/dev/null; then
            log "尝试通过 pip 安装 uvicorn..."
            pip3 install uvicorn[standard] 2>/dev/null || pip install uvicorn[standard]
        else
            err "未找到 python3，请先安装 Python 3.14"
            exit 1
        fi
    fi

    # 检查后端依赖（requirements.txt）
    if [[ -f "${PROJECT_DIR}/src/requirements.txt" ]]; then
        log "安装后端依赖..."
        pip3 install -r "${PROJECT_DIR}/src/requirements.txt" -q 2>/dev/null || \
            pip install -r "${PROJECT_DIR}/src/requirements.txt" -q
    fi

    # 使用 nohup 启动后端，确保独立于终端运行
    log "启动 FastAPI 服务 (nohup uvicorn)..."
    cd "${PROJECT_DIR}/src"

    nohup uvicorn api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        > "${BACKEND_LOG}" 2>&1 &

    local backend_pid=$!
    echo "${backend_pid}" > "${BACKEND_PID_FILE}"

    log "后端进程 PID: ${backend_pid}，日志: ${BACKEND_LOG}"

    # 健康检查：轮询等待后端就绪
    local retries=0
    local max_retries=30
    local health_url="http://localhost:8000/api/health"

    log "等待后端就绪 (最多 ${max_retries} 秒)..."

    while [[ ${retries} -lt ${max_retries} ]]; do
        if curl -sf "${health_url}" >/dev/null 2>&1; then
            ok "后端服务已就绪 — ${health_url}"
            return 0
        fi

        # 检查进程是否还在运行
        if ! kill -0 "${backend_pid}" 2>/dev/null; then
            err "后端进程 (PID: ${backend_pid}) 已退出"
            err "日志输出:"
            tail -n 30 "${BACKEND_LOG}" >&2
            exit 1
        fi

        sleep 1
        ((retries++))
        echo -n "."
    done

    echo ""
    err "后端服务健康检查超时 (${max_retries} 秒)"
    err "请检查日志: ${BACKEND_LOG}"
    tail -n 30 "${BACKEND_LOG}" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# 前端启动函数
# ---------------------------------------------------------------------------
start_frontend() {
    step "启动前端服务 (Vite)"

    # 端口冲突检查
    check_port 5173 "Vite Dev Server"

    local frontend_dir="${PROJECT_DIR}/frontend"
    cd "${frontend_dir}"

    # node_modules 检查
    if [[ ! -d "${frontend_dir}/node_modules/.bin/vite" && ! -f "${frontend_dir}/node_modules/.bin/vite" ]]; then
        warn "未找到 node_modules，即将执行 npm install..."
        if ! command -v npm &>/dev/null; then
            err "未找到 npm，请先安装 Node.js"
            exit 1
        fi
        npm install
        ok "npm install 完成"
    else
        ok "node_modules 已存在"
    fi

    # 启动前端
    log "启动 Vite 开发服务器..."
    nohup npm run dev \
        > "${FRONTEND_LOG}" 2>&1 &

    local frontend_pid=$!
    echo "${frontend_pid}" > "${LOG_DIR}/frontend.pid"
    log "前端进程 PID: ${frontend_pid}，日志: ${FRONTEND_LOG}"

    # 等待前端就绪
    local retries=0
    local max_retries=15

    log "等待前端就绪 (最多 ${max_retries} 秒)..."

    while [[ ${retries} -lt ${max_retries} ]]; do
        if curl -sf "http://localhost:5173" >/dev/null 2>&1; then
            ok "前端服务已就绪 — http://localhost:5173"
            return 0
        fi

        # 检查进程是否还在运行
        if ! kill -0 "${frontend_pid}" 2>/dev/null; then
            err "前端进程 (PID: ${frontend_pid}) 已退出"
            err "日志输出:"
            tail -n 30 "${FRONTEND_LOG}" >&2
            exit 1
        fi

        sleep 1
        ((retries++))
        echo -n "."
    done

    echo ""
    # 前端可能只是还没完全就绪，但 Vite 通常启动很快，给个警告继续
    warn "前端服务可能尚未完全就绪，请稍等片刻"
    log "前端日志: ${FRONTEND_LOG}"
}

# ---------------------------------------------------------------------------
# 自动打开浏览器
# ---------------------------------------------------------------------------
open_browser() {
    step "打开浏览器"
    local url="http://localhost:5173"

    if command -v open &>/dev/null; then
        log "正在打开浏览器: ${url}"
        sleep 1
        open "${url}"
        ok "浏览器已启动"
    else
        warn "未找到 'open' 命令，请手动访问: ${url}"
    fi
}

# ---------------------------------------------------------------------------
# 打印服务状态
# ---------------------------------------------------------------------------
print_status() {
    step "服务启动概览"

    local backend_pid="未运行"
    local frontend_pid="未运行"

    if [[ -f "${BACKEND_PID_FILE}" ]]; then
        local pid
        pid=$(cat "${BACKEND_PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            backend_pid="${pid} ${GREEN}(运行中)${NC}"
        else
            backend_pid="${pid} ${RED}(已退出)${NC}"
        fi
    fi

    if [[ -f "${LOG_DIR}/frontend.pid" ]]; then
        local pid
        pid=$(cat "${LOG_DIR}/frontend.pid")
        if kill -0 "${pid}" 2>/dev/null; then
            frontend_pid="${pid} ${GREEN}(运行中)${NC}"
        else
            frontend_pid="${pid} ${RED}(已退出)${NC}"
        fi
    fi

    echo -e "  ${CYAN}后端:${NC}  http://localhost:8000    PID: ${backend_pid}"
    echo -e "  ${CYAN}前端:${NC}  http://localhost:5173    PID: ${frontend_pid}"
    echo -e "  ${CYAN}日志:${NC}  ${LOG_DIR}/"
    echo -e ""
    echo -e "  ${GREEN}🚀 启动完成！浏览器已自动打开${NC}"
    echo -e ""
    echo -e "  ${YELLOW}提示:${NC}"
    echo -e "    - 查看后端日志: ${BOLD}tail -f ${BACKEND_LOG}${NC}"
    echo -e "    - 查看前端日志: ${BOLD}tail -f ${FRONTEND_LOG}${NC}"
    echo -e "    - 停止服务:      ${BOLD}bash stop.sh${NC}"
}

# ---------------------------------------------------------------------------
# 信号处理：脚本退出时清理
# ---------------------------------------------------------------------------
trap 'echo ""; warn "脚本中断"; exit 130' SIGINT SIGTERM

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
clear
echo -e "${BOLD}"
echo "    ██╗ █████╗  ██████╗  ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗"
echo "    ██║██╔══██╗██╔═══██╗██╔═══██╗██║   ██║██╔══██╗████╗  ██║"
echo "    ██║███████║██║   ██║██║   ██║██║   ██║███████║██╔██╗ ██║"
echo "    ██║██╔══██║██║   ██║██║   ██║╚██╗ ██╔╝██╔══██║██║╚██╗██║"
echo "    ██║██║  ██║╚██████╔╝╚██████╔╝ ╚████╔╝ ██║  ██║██║ ╚████║"
echo "    ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝"
echo -e "${NC}"
echo -e "  ${BOLD}教员AI顾问 - 一键启动脚本${NC}"
echo -e "  ========================================="
echo -e ""

start_backend
start_frontend
open_browser
print_status

exit 0
