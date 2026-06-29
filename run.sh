#!/bin/bash
set -e

# =============================================================================
# 一键启动脚本：同时启动后端(FastAPI)和前端(Vite)
# 适用环境：macOS M5, Python 3.14, Node.js/npm
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'
NC='\033[0m'; BOLD='\033[1m'

log()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
err()  { echo -e "${RED}[ERR]${NC}  $1" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
step() { echo -e ""; echo -e "${BOLD}${MAGENTA}==>${NC} ${BOLD}$1${NC}"; }

# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"

step "项目目录"
log "${PROJECT_DIR}"
ok "验证通过"

> "${BACKEND_LOG}"; > "${FRONTEND_LOG}"

# ---------------------------------------------------------------------------
check_port() {
    local port=$1 service=$2
    if lsof -Pi ":${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pid=$(lsof -Pi ":${port}" -sTCP:LISTEN -t 2>/dev/null | head -n1)
        err "端口 ${port} 被占用 (PID: ${pid}) — ${service}"
        err "先执行: bash stop.sh"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 检测 uvicorn：尝试多种方式，哪个能用用哪个
detect_uvicorn() {
    local uvicorn_cmd=""

    # 方式1: PATH 中的 uvicorn 命令（你之前可能用的就是这个）
    if command -v uvicorn &>/dev/null; then
        uvicorn_cmd="uvicorn"
        ok "uvicorn: $(uvicorn --version 2>&1)"
        echo "${uvicorn_cmd}"
        return 0
    fi

    # 方式2: python3 -m uvicorn
    if command -v python3 &>/dev/null && python3 -m uvicorn --version &>/dev/null 2>&1; then
        uvicorn_cmd="python3 -m uvicorn"
        ok "uvicorn: $(python3 -m uvicorn --version 2>&1)"
        echo "${uvicorn_cmd}"
        return 0
    fi

    # 方式3: python -m uvicorn
    if command -v python &>/dev/null && python -m uvicorn --version &>/dev/null 2>&1; then
        uvicorn_cmd="python -m uvicorn"
        ok "uvicorn: $(python -m uvicorn --version 2>&1)"
        echo "${uvicorn_cmd}"
        return 0
    fi

    # 方式4: 虚拟环境
    local venv_paths=("${PROJECT_DIR}/venv/bin/uvicorn" "${PROJECT_DIR}/.venv/bin/uvicorn")
    for v in "${venv_paths[@]}"; do
        if [[ -x "$v" ]]; then
            ok "uvicorn: ${v}"
            echo "${v}"
            return 0
        fi
    done

    # 全部失败
    err "未找到 uvicorn"
    echo ""
    echo -e "  ${YELLOW}请手动安装:${NC}"
    echo -e "    python3 -m pip install uvicorn[standard]"
    echo -e "  或:"
    echo -e "    pip3 install uvicorn[standard]"
    echo ""
    echo -e "  如果你用了虚拟环境:"
    echo -e "    source venv/bin/activate"
    echo -e "    pip install uvicorn[standard]"
    echo ""
    return 1
}

# ---------------------------------------------------------------------------
start_backend() {
    step "启动后端"
    check_port 8000 "FastAPI"

    local uvicorn_cmd
    uvicorn_cmd=$(detect_uvicorn) || exit 1

    log "nohup ${uvicorn_cmd} api.main:app"
    cd "${PROJECT_DIR}/src"
    nohup ${uvicorn_cmd} api.main:app --host 0.0.0.0 --port 8000 --reload > "${BACKEND_LOG}" 2>&1 &

    local pid=$!
    echo "${pid}" > "${BACKEND_PID_FILE}"

    local retries=0 max=30
    log "等待后端就绪..."
    while [[ ${retries} -lt ${max} ]]; do
        if curl -sf "http://localhost:8000/api/health" >/dev/null 2>&1; then
            ok "后端就绪"
            return 0
        fi
        if ! kill -0 "${pid}" 2>/dev/null; then
            err "后端进程退出"
            tail -n 30 "${BACKEND_LOG}" >&2
            exit 1
        fi
        sleep 1; ((retries++)); echo -n "."
    done
    err "后端超时"; tail -n 30 "${BACKEND_LOG}" >&2; exit 1
}

# ---------------------------------------------------------------------------
start_frontend() {
    step "启动前端"
    check_port 5173 "Vite"

    cd "${PROJECT_DIR}/frontend"

    if [[ ! -f "node_modules/.bin/vite" ]]; then
        warn "npm install..."
        npm install
        ok "npm install 完成"
    else
        ok "node_modules 已存在"
    fi

    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    local pid=$!
    echo "${pid}" > "${LOG_DIR}/frontend.pid"

    local retries=0 max=15
    log "等待前端就绪..."
    while [[ ${retries} -lt ${max} ]]; do
        if curl -sf "http://localhost:5173" >/dev/null 2>&1; then
            ok "前端就绪"; return 0
        fi
        if ! kill -0 "${pid}" 2>/dev/null; then
            err "前端进程退出"; tail -n 30 "${FRONTEND_LOG}" >&2; exit 1
        fi
        sleep 1; ((retries++)); echo -n "."
    done
    warn "前端可能还在启动中"
}

# ---------------------------------------------------------------------------
open_browser() {
    step "打开浏览器"
    if command -v open &>/dev/null; then
        sleep 1; open "http://localhost:5173"; ok "已打开"
    fi
}

# ---------------------------------------------------------------------------
print_status() {
    step "服务状态"
    local bp="未运行" fp="未运行"
    if [[ -f "${BACKEND_PID_FILE}" ]]; then
        local p=$(cat "${BACKEND_PID_FILE}")
        kill -0 "$p" 2>/dev/null && bp="${p} ${GREEN}(运行中)${NC}" || bp="${p} ${RED}(已退出)${NC}"
    fi
    if [[ -f "${LOG_DIR}/frontend.pid" ]]; then
        local p=$(cat "${LOG_DIR}/frontend.pid")
        kill -0 "$p" 2>/dev/null && fp="${p} ${GREEN}(运行中)${NC}" || fp="${p} ${RED}(已退出)${NC}"
    fi
    echo -e "  后端: http://localhost:8000  PID: ${bp}"
    echo -e "  前端: http://localhost:5173  PID: ${fp}"
    echo ""
    echo -e "  ${GREEN}🚀 启动完成！${NC}"
    echo ""
    echo -e "  ${YELLOW}提示:${NC}"
    echo -e "    日志:    tail -f ${BACKEND_LOG}"
    echo -e "    停止:    bash stop.sh"
}

# ---------------------------------------------------------------------------
trap 'echo ""; warn "中断"; exit 130' SIGINT SIGTERM

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
echo ""

start_backend
start_frontend
open_browser
print_status

exit 0
