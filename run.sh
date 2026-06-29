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
step() { echo ""; echo -e "${BOLD}${MAGENTA}==>${NC} ${BOLD}$1${NC}"; }

# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"

step "项目目录: ${PROJECT_DIR}"

> "${BACKEND_LOG}"; > "${FRONTEND_LOG}"

# ---------------------------------------------------------------------------
# 强制清理残留进程（避免 "Address already in use"）
# ---------------------------------------------------------------------------
cleanup_residual() {
    log "清理残留进程..."

    # 从 PID 文件停止
    for pid_file in "${BACKEND_PID_FILE}" "${LOG_DIR}/frontend.pid"; do
        if [[ -f "${pid_file}" ]]; then
            local old_pid=$(cat "${pid_file}" 2>/dev/null)
            if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
                kill "${old_pid}" 2>/dev/null || true
                sleep 1
                kill -9 "${old_pid}" 2>/dev/null || true
            fi
            rm -f "${pid_file}"
        fi
    done

    # 兜底：直接杀端口对应的进程
    for port in 8000 5173; do
        local pids=$(lsof -Pi ":${port}" -sTCP:LISTEN -t 2>/dev/null)
        if [[ -n "${pids}" ]]; then
            warn "端口 ${port} 仍有残留进程，强制清理..."
            echo "${pids}" | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
    done

    ok "残留进程清理完成"
}

# ---------------------------------------------------------------------------
check_port() {
    local port=$1 service=$2
    if lsof -Pi ":${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pid=$(lsof -Pi ":${port}" -sTCP:LISTEN -t 2>/dev/null | head -n1)
        err "端口 ${port} 仍被占用 (PID: ${pid}) — ${service}"
        err "请手动释放端口: kill -9 ${pid}"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 检测 uvicorn —— 输出到 stdout 的只有命令路径，日志走 stderr
detect_uvicorn() {
    # 1. PATH 中的 uvicorn
    local uvicorn_path
    uvicorn_path=$(command -v uvicorn 2>/dev/null)
    if [[ -n "${uvicorn_path}" ]]; then
        echo "uvicorn"
        return 0
    fi

    # 2. python3 -m uvicorn
    if command -v python3 &>/dev/null; then
        if python3 -m uvicorn --version &>/dev/null 2>&1; then
            echo "python3 -m uvicorn"
            return 0
        fi
    fi

    # 3. python -m uvicorn
    if command -v python &>/dev/null; then
        if python -m uvicorn --version &>/dev/null 2>&1; then
            echo "python -m uvicorn"
            return 0
        fi
    fi

    # 4. 虚拟环境 —— 用 python3 -m uvicorn 更可靠
    if [[ -x "${PROJECT_DIR}/.venv/bin/python3" ]]; then
        if "${PROJECT_DIR}/.venv/bin/python3" -m uvicorn --version &>/dev/null 2>&1; then
            echo "${PROJECT_DIR}/.venv/bin/python3 -m uvicorn"
            return 0
        fi
    fi
    if [[ -x "${PROJECT_DIR}/venv/bin/python3" ]]; then
        if "${PROJECT_DIR}/venv/bin/python3" -m uvicorn --version &>/dev/null 2>&1; then
            echo "${PROJECT_DIR}/venv/bin/python3 -m uvicorn"
            return 0
        fi
    fi

    # 全部失败
    err "未找到 uvicorn"
    echo "" >&2
    echo -e "  ${YELLOW}请安装:${NC}" >&2
    echo -e "    python3 -m pip install uvicorn[standard]" >&2
    echo -e "  或激活虚拟环境:" >&2
    echo -e "    source .venv/bin/activate && pip install uvicorn[standard]" >&2
    echo "" >&2
    return 1
}

# ---------------------------------------------------------------------------
start_backend() {
    step "启动后端"
    check_port 8000 "FastAPI"

    local uvicorn_cmd
    uvicorn_cmd=$(detect_uvicorn) || exit 1
    ok "uvicorn: ${uvicorn_cmd}"

    log "启动: nohup ${uvicorn_cmd} api.main:app"
    cd "${PROJECT_DIR}/src"
    nohup ${uvicorn_cmd} api.main:app --host 0.0.0.0 --port 8000 --reload > "${BACKEND_LOG}" 2>&1 &

    local pid=$!
    echo "${pid}" > "${BACKEND_PID_FILE}"

    local retries=0 max=30
    log "等待后端就绪 (最多 ${max} 秒)..."
    while [[ ${retries} -lt ${max} ]]; do
        if curl -sf "http://localhost:8000/api/health" >/dev/null 2>&1; then
            ok "后端就绪"
            return 0
        fi
        if ! kill -0 "${pid}" 2>/dev/null; then
            err "后端进程已退出"
            tail -n 50 "${BACKEND_LOG}" >&2
            exit 1
        fi
        sleep 1; ((retries++)); echo -n "."
    done
    err "后端超时"; tail -n 50 "${BACKEND_LOG}" >&2; exit 1
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

    log "启动: npm run dev"
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
        sleep 1; open "http://localhost:5173"; ok "浏览器已打开"
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
    echo -e "    日志: tail -f ${BACKEND_LOG}"
    echo -e "    停止: bash stop.sh"
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

# ===== 启动前强制清理残留进程 =====
cleanup_residual

start_backend
start_frontend
open_browser
print_status

exit 0
