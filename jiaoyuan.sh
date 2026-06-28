#!/bin/bash
# 教员AI顾问 - 真正的一键启动脚本
# 零手动操作，自动处理环境、同步代码、安装依赖、启动服务

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="qwen3:30b-a3b"
API_PORT=8000
FE_PORT=5173

# ========================================================================
# 日志函数
# ========================================================================
log_info()  { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_step()  { echo -e "\n${CYAN}▶ $1${NC}"; }

# ========================================================================
# 检查命令是否存在
# ========================================================================
command_exists() { command -v "$1" &> /dev/null; }

# ========================================================================
# 停止已运行的服务
# ========================================================================
kill_existing() {
    log_step "清理已有进程..."
    
    # 尝试从 PID 文件停止
    if [ -f "$SCRIPT_DIR/.backend.pid" ]; then
        OLD_PID=$(cat "$SCRIPT_DIR/.backend.pid" 2>/dev/null || echo "")
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            kill "$OLD_PID" 2>/dev/null
            log_warn "已停止旧的后端进程 (PID: $OLD_PID)"
        fi
        rm -f "$SCRIPT_DIR/.backend.pid"
    fi
    
    if [ -f "$SCRIPT_DIR/.frontend.pid" ]; then
        OLD_PID=$(cat "$SCRIPT_DIR/.frontend.pid" 2>/dev/null || echo "")
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            kill "$OLD_PID" 2>/dev/null
            log_warn "已停止旧的前端进程 (PID: $OLD_PID)"
        fi
        rm -f "$SCRIPT_DIR/.frontend.pid"
    fi
    
    # 强制清理可能残留的进程
    sleep 1
    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    
    log_info "进程清理完成"
}

# ========================================================================
# 检查 Python 版本（必须 3.12+，因为 f-string 转义问题）
# ========================================================================
check_python() {
    log_step "检查 Python 环境"
    
    if ! command_exists python3; then
        log_error "未找到 python3"
        log_error "macOS 安装: brew install python@3.12"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    
    log_info "Python 版本: $PYTHON_VERSION"
    
    if [ "$MAJOR" -lt 3 ] || [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 12 ]; then
        log_error "❌ 需要 Python 3.12+"
        log_error "代码中使用了 f-string \\n 转义，Python 3.11 及以下会报 SyntaxError"
        log_error "请安装: brew install python@3.12"
        log_error "然后设置: export PATH=\"/opt/homebrew/opt/python@3.12/libexec/bin:\$PATH\""
        exit 1
    fi
    
    log_info "Python 3.12+ 检查通过 ✓"
}

# ========================================================================
# 检查 Node.js
# ========================================================================
check_node() {
    log_step "检查 Node.js 环境"
    if ! command_exists node; then
        log_error "未找到 Node.js"
        log_error "安装: brew install node"
        exit 1
    fi
    NODE_VERSION=$(node --version)
    log_info "Node.js 版本: $NODE_VERSION ✓"
}

# ========================================================================
# 检查并启动 Ollama
# ========================================================================
check_ollama() {
    log_step "检查 Ollama 服务"
    if ! command_exists ollama; then
        log_error "Ollama 未安装"
        log_error "安装: curl -fsSL https://ollama.com/install.sh | sh"
        exit 1
    fi

    # 检查 Ollama 是否运行
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_warn "Ollama 未运行，正在启动..."
        ollama serve > /dev/null 2>&1 &
        
        # 等待服务启动
        for i in {1..30}; do
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            log_error "Ollama 启动失败，请手动运行: ollama serve"
            exit 1
        fi
    fi
    log_info "Ollama 服务运行中 ✓"

    # 检查模型
    log_step "检查模型: $MODEL"
    if ! curl -s http://localhost:11434/api/tags | grep -q "$MODEL"; then
        log_warn "模型未下载，正在下载 (约 15-20GB)..."
        ollama pull "$MODEL"
        log_info "模型下载完成 ✓"
    else
        log_info "模型 $MODEL 已就绪 ✓"
    fi
}

# ========================================================================
# 同步 GitHub 最新代码（自动处理冲突）
# ========================================================================
sync_code() {
    log_step "同步 GitHub 最新代码"
    cd "$SCRIPT_DIR"
    
    if [ -d ".git" ]; then
        # 强制丢弃本地未提交的修改，拉取最新
        git fetch origin main
        
        # 检查是否有本地未提交修改
        if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null; then
            log_warn "检测到本地未提交修改，正在丢弃..."
            git reset --hard HEAD
        fi
        
        git checkout main 2>/dev/null || git checkout -b main
        git reset --hard origin/main
        git pull origin main
        log_info "代码已同步到最新 ✓"
    else
        log_error "当前目录不是 Git 仓库，请确保代码已克隆"
        exit 1
    fi
}

# ========================================================================
# 配置 Python 虚拟环境
# ========================================================================
setup_venv() {
    log_step "配置 Python 虚拟环境"
    cd "$SCRIPT_DIR"

    if [ ! -d ".venv" ]; then
        log_info "创建虚拟环境..."
        python3 -m venv .venv
    fi

    source .venv/bin/activate
    log_info "虚拟环境已激活 ✓"
}

# ========================================================================
# 安装后端依赖
# ========================================================================
install_backend_deps() {
    log_step "安装后端依赖"
    cd "$SCRIPT_DIR"
    source .venv/bin/activate

    pip install -q --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        pip install -q -r requirements.txt
        log_info "后端依赖安装完成 ✓"
    else
        log_error "未找到 requirements.txt"
        exit 1
    fi
}

# ========================================================================
# 构建知识库向量索引
# ========================================================================
build_vector_index() {
    log_step "检查知识库索引"
    cd "$SCRIPT_DIR"
    source .venv/bin/activate

    if [ ! -d "data/maoxuan/chroma_db" ] || [ ! -f "data/maoxuan/chroma_db/chroma.sqlite3" ]; then
        log_info "首次运行，构建向量索引（约 1-2 分钟）..."
        python3 -c "
import sys
sys.path.insert(0, 'src')
from core.maoxuan_retriever import MaoxuanRetriever
retriever = MaoxuanRetriever()
retriever.build_index()
print('✓ 向量索引构建完成')
"
    else
        log_info "向量索引已存在 ✓"
    fi
}

# ========================================================================
# 安装前端依赖
# ========================================================================
install_frontend_deps() {
    log_step "安装前端依赖"
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log_info "首次安装，npm install 运行中..."
        npm install
    else
        log_info "node_modules 已存在 ✓"
    fi
}

# ========================================================================
# 启动后端服务
# ========================================================================
start_backend() {
    log_step "启动后端服务 (端口 $API_PORT)"
    cd "$SCRIPT_DIR"
    source .venv/bin/activate

    mkdir -p logs

    # 关键：PYTHONPATH=src 使 api 模块可导入
    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
    export OLLAMA_HOST="http://localhost:11434"
    export MODEL_NAME="$MODEL"
    export API_HOST="0.0.0.0"
    export API_PORT="$API_PORT"
    export LOG_LEVEL="INFO"
    export ENABLE_THINKING="true"
    export LLM_TIMEOUT="60"
    export MAX_FULL_TURNS="10"
    export CORS_ORIGINS="http://localhost:$FE_PORT,http://127.0.0.1:$FE_PORT"

    nohup python3 -m uvicorn api.main:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --log-level warning \
        > logs/backend.log 2>&1 &

    BACKEND_PID=$!
    echo $BACKEND_PID > "$SCRIPT_DIR/.backend.pid"
    log_info "后端进程 PID: $BACKEND_PID"

    # 等待后端启动并验证
    log_info "等待后端启动..."
    for i in {1..30}; do
        if curl -s http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
            log_info "后端服务已就绪 ✓"
            return 0
        fi
        if ! kill -0 $BACKEND_PID 2>/dev/null; then
            log_error "后端进程已退出，查看日志:"
            tail -n 50 "$SCRIPT_DIR/logs/backend.log" 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done

    log_error "后端启动超时，日志:"
    tail -n 50 "$SCRIPT_DIR/logs/backend.log" 2>/dev/null || true
    exit 1
}

# ========================================================================
# 启动前端服务
# ========================================================================
start_frontend() {
    log_step "启动前端服务 (端口 $FE_PORT)"
    cd "$SCRIPT_DIR/frontend"

    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$SCRIPT_DIR/.frontend.pid"
    log_info "前端进程 PID: $FRONTEND_PID"

    sleep 3
    
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        log_error "前端启动失败，日志:"
        tail -n 30 "$SCRIPT_DIR/logs/frontend.log" 2>/dev/null || true
        exit 1
    fi
    
    log_info "前端服务已启动 ✓"
}

# ========================================================================
# 清理函数（Ctrl+C 时调用）
# ========================================================================
cleanup() {
    echo -e "\n${YELLOW}[!] 正在停止所有服务...${NC}"
    
    if [ -f "$SCRIPT_DIR/.backend.pid" ]; then
        PID=$(cat "$SCRIPT_DIR/.backend.pid" 2>/dev/null || echo "")
        [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
        rm -f "$SCRIPT_DIR/.backend.pid"
    fi
    
    if [ -f "$SCRIPT_DIR/.frontend.pid" ]; then
        PID=$(cat "$SCRIPT_DIR/.frontend.pid" 2>/dev/null || echo "")
        [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
        rm -f "$SCRIPT_DIR/.frontend.pid"
    fi
    
    pkill -f "uvicorn api.main:app" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    
    echo -e "${GREEN}[✓] 所有服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ========================================================================
# 主流程
# ========================================================================
clear
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║           教员AI顾问 - 真正的一键启动脚本                      ║"
echo "║                                                              ║"
echo "║   自动处理：环境检查 → 代码同步 → 依赖安装 → 启动服务           ║"
echo "║              模型: qwen3:30b-a3b | 内存: 24GB                   ║"
echo "║                                                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

kill_existing
check_python
check_node
check_ollama
sync_code
setup_venv
install_backend_deps
build_vector_index
install_frontend_deps
start_backend
start_frontend

# 打印访问信息
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║                    🎉 所有服务已启动！                        ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  🌐 前端界面: http://localhost:$FE_PORT                           ║${NC}"
echo -e "${GREEN}║  🔌 API 文档: http://localhost:$API_PORT/docs                     ║${NC}"
echo -e "${GREEN}║  💓 健康检查: http://localhost:$API_PORT/api/health                ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  日志查看：                                                   ║${NC}"
echo -e "${GREEN}║    tail -f logs/backend.log  (后端日志)                      ║${NC}"
echo -e "${GREEN}║    tail -f logs/frontend.log (前端日志)                      ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  按 Ctrl+C 停止所有服务                                      ║${NC}"
echo -e "${GREEN}║                                                              ║"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"

# 保持脚本运行
while true; do
    sleep 1
done
