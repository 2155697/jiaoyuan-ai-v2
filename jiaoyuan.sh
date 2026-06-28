#!/bin/bash
# 教员AI顾问 - 一键启动脚本
# 适配 Mac M5 24GB，模型 qwen3:30b-a3b

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="jiaoyuan-ai-v2"
MODEL="qwen3:30b-a3b"
API_PORT=8000
FE_PORT=5173

# ============================================================================
# 日志函数
# ============================================================================
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}▶ $1${NC}"; }

# ============================================================================
# 检查命令是否存在
# ============================================================================
command_exists() { command -v "$1" &> /dev/null; }

# ============================================================================
# 检查 Python 版本
# ============================================================================
check_python() {
    log_step "检查 Python 环境"
    if ! command_exists python3; then
        log_error "未找到 python3，请先安装 Python 3.12+"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "Python 版本: $PYTHON_VERSION"

    # 检查是否 >= 3.12
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]); then
        log_warn "推荐 Python 3.12+，当前为 $PYTHON_VERSION"
        log_warn "f-string 中 \n 转义在 3.12 以下会导致 SyntaxError"
        read -p "是否继续? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ============================================================================
# 检查 Node.js
# ============================================================================
check_node() {
    log_step "检查 Node.js 环境"
    if ! command_exists node; then
        log_error "未找到 node，请先安装 Node.js (推荐 v18+)"
        log_error "运行: brew install node"
        exit 1
    fi
    NODE_VERSION=$(node --version)
    log_info "Node.js 版本: $NODE_VERSION"

    if ! command_exists npm; then
        log_error "未找到 npm"
        exit 1
    fi
    log_info "npm 版本: $(npm --version)"
}

# ============================================================================
# 检查 Ollama
# ============================================================================
check_ollama() {
    log_step "检查 Ollama 服务"
    if ! command_exists ollama; then
        log_error "未找到 ollama，请先安装"
        log_error "运行: curl -fsSL https://ollama.com/install.sh | sh"
        exit 1
    fi

    # 检查 Ollama 是否运行
    if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
        log_warn "Ollama 服务未运行，尝试启动..."
        ollama serve &
        sleep 3
        if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
            log_error "Ollama 启动失败，请手动运行: ollama serve"
            exit 1
        fi
    fi
    log_info "Ollama 服务运行正常"

    # 检查模型是否已下载
    log_step "检查模型: $MODEL"
    if ! curl -s http://localhost:11434/api/tags | grep -q "$MODEL"; then
        log_warn "模型 $MODEL 未下载，开始下载..."
        log_warn "首次下载约需 15-20GB 磁盘空间，请耐心等待"
        ollama pull "$MODEL"
    else
        log_info "模型 $MODEL 已就绪"
    fi
}

# ============================================================================
# 设置环境变量
# ============================================================================
setup_env() {
    log_step "配置环境变量"
    export OLLAMA_HOST="http://localhost:11434"
    export MODEL_NAME="$MODEL"
    export API_HOST="0.0.0.0"
    export API_PORT="$API_PORT"
    export LOG_LEVEL="INFO"
    export ENABLE_THINKING="true"
    export LLM_TIMEOUT="60"
    export MAX_FULL_TURNS="10"
    export CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

    log_info "MODEL_NAME=$MODEL"
    log_info "API_PORT=$API_PORT"
}

# ============================================================================
# 安装后端依赖
# ============================================================================
setup_backend() {
    log_step "配置 Python 虚拟环境"
    cd "$SCRIPT_DIR"

    if [ ! -d ".venv" ]; then
        log_info "创建虚拟环境 .venv..."
        python3 -m venv .venv
    fi

    source .venv/bin/activate

    log_info "安装/更新后端依赖..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt

    log_info "后端依赖就绪"
}

# ============================================================================
# 构建向量索引
# ============================================================================
build_index() {
    log_step "检查知识库索引"
    if [ ! -d "data/maoxuan/chroma_db" ] || [ -z "$(ls -A data/maoxuan/chroma_db 2>/dev/null)" ]; then
        log_info "构建毛选向量索引（首次运行）..."
        python3 -c "
import sys
sys.path.insert(0, 'src/core')
from maoxuan_retriever import MaoxuanRetriever
retriever = MaoxuanRetriever()
retriever.build_index()
print('向量索引构建完成')
"
    else
        log_info "向量索引已存在"
    fi
}

# ============================================================================
# 安装前端依赖
# ============================================================================
setup_frontend() {
    log_step "配置前端依赖"
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖（首次运行，约需 1-2 分钟）..."
        npm install
    else
        log_info "前端依赖已安装"
    fi
}

# ============================================================================
# 启动服务
# ============================================================================
start_backend() {
    log_step "启动后端服务 (端口 $API_PORT)"
    cd "$SCRIPT_DIR"
    source .venv/bin/activate

    # 使用后台进程启动
    nohup python3 -m uvicorn api.main:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --log-level warning \
        > logs/backend.log 2>&1 &

    BACKEND_PID=$!
    echo $BACKEND_PID > .backend.pid
    log_info "后端 PID: $BACKEND_PID"

    # 等待后端启动
    for i in {1..30}; do
        if curl -s http://localhost:$API_PORT/api/health &> /dev/null; then
            log_info "后端服务已就绪"
            return 0
        fi
        sleep 1
    done
    log_error "后端启动超时，请检查 logs/backend.log"
    exit 1
}

start_frontend() {
    log_step "启动前端服务 (端口 $FE_PORT)"
    cd "$SCRIPT_DIR/frontend"

    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../.frontend.pid
    log_info "前端 PID: $FRONTEND_PID"

    sleep 3
    log_info "前端服务已启动"
}

# ============================================================================
# 清理函数
# ============================================================================
cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"
    
    # 停止前端
    if [ -f "$SCRIPT_DIR/.frontend.pid" ]; then
        FRONTEND_PID=$(cat "$SCRIPT_DIR/.frontend.pid")
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            kill "$FRONTEND_PID" 2>/dev/null
            log_info "前端已停止 (PID: $FRONTEND_PID)"
        fi
        rm -f "$SCRIPT_DIR/.frontend.pid"
    fi
    
    # 停止后端
    if [ -f "$SCRIPT_DIR/.backend.pid" ]; then
        BACKEND_PID=$(cat "$SCRIPT_DIR/.backend.pid")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            kill "$BACKEND_PID" 2>/dev/null
            log_info "后端已停止 (PID: $BACKEND_PID)"
        fi
        rm -f "$SCRIPT_DIR/.backend.pid"
    fi
    
    echo -e "${GREEN}所有服务已停止${NC}"
    exit 0
}

# 捕获 Ctrl+C 和终止信号
trap cleanup SIGINT SIGTERM

# ============================================================================
# 创建日志目录
# ============================================================================
mkdir -p "$SCRIPT_DIR/logs"

# ============================================================================
# 主流程
# ============================================================================
clear
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          教员AI顾问 - 一键启动脚本 (Mac M5 适配版)            ║"
echo "║              模型: qwen3:30b-a3b | 内存: 24GB                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

check_python
check_node
check_ollama
setup_env
setup_backend
build_index
setup_frontend

start_backend
start_frontend

# ============================================================================
# 打印访问信息
# ============================================================================
echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    🎉 所有服务已启动！                       ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  🌐 前端界面: http://localhost:$FE_PORT                           ║${NC}"
echo -e "${GREEN}║  🔌 API 文档: http://localhost:$API_PORT/docs                     ║${NC}"
echo -e "${GREEN}║  💓 健康检查: http://localhost:$API_PORT/api/health                ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  快捷操作:                                                   ║${NC}"
echo -e "${GREEN}║    查看后端日志: tail -f logs/backend.log                    ║${NC}"
echo -e "${GREEN}║    查看前端日志: tail -f logs/frontend.log                   ║${NC}"
echo -e "${GREEN}║    停止服务:    ./stop.sh                                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"

# 保持脚本在前台运行，等待用户按 Ctrl+C
log_info "按 Ctrl+C 停止所有服务"
while true; do
    sleep 1
done
