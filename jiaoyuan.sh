#!/bin/bash
# =====================================================================
# 教员AI顾问 - 一键启动脚本（Jiaoyuan.sh）
# 功能：检测环境 → 安装Ollama → 创建虚拟环境 → 安装依赖 → 构建知识库 → 启动后端 → 打开浏览器
# 用法：chmod +x jiaoyuan.sh && ./jiaoyuan.sh
# 版本: 3.0.1
# =====================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step=0
info()  { echo -e "${BLUE}[$(printf "%02d" $step)]${NC} $1"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
err()   { echo -e "  ${RED}✗${NC} $1"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# ====================
# 1. 检查 Python
# ====================
step=1
info "检查 Python 3.10+..."
if ! command_exists python3; then
    err "未找到 python3，请先安装 Python 3.10+"
    exit 1
fi
PYVER=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
PYMIN=$(python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)") || {
    err "Python 版本 ${PYVER} 太低，需要 3.10+"
    exit 1
}
ok "Python ${PYVER}"

# ====================
# 2. 检查 Ollama
# ====================
step=2
info "检查 Ollama..."
if ! command_exists ollama; then
    warn "Ollama 未安装，正在自动安装..."
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama 安装完成"
else
    ok "Ollama 已安装"
fi

# 检查 Ollama 服务是否运行
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    warn "Ollama 服务未运行，正在启动..."
    ollama serve &
    sleep 4
fi
ok "Ollama 服务运行中"

# ====================
# 3. 检查/下载模型
# ====================
step=3

# 从 .env 读取模型名（默认 qwen3:8b）
MODEL_NAME="qwen3:8b"
if [ -f ".env" ]; then
    ENV_MODEL=$(grep -E "^MODEL_NAME=" .env | head -1 | cut -d'=' -f2 | tr -d ' ')
    [ -n "$ENV_MODEL" ] && MODEL_NAME="$ENV_MODEL"
fi

info "检查模型: ${MODEL_NAME}..."
if ollama list 2>/dev/null | grep -q "${MODEL_NAME}"; then
    ok "模型 ${MODEL_NAME} 已存在"
else
    warn "模型 ${MODEL_NAME} 未下载，正在拉取（首次需要几分钟，请等待）..."
    ollama pull "${MODEL_NAME}" || {
        err "模型下载失败，请检查网络或手动执行: ollama pull ${MODEL_NAME}"
        exit 1
    }
    ok "模型 ${MODEL_NAME} 下载完成"
fi

# ====================
# 4. 创建虚拟环境
# ====================
step=4
info "检查虚拟环境..."
if [ ! -d ".venv" ]; then
    warn "创建虚拟环境 .venv..."
    python3 -m venv .venv
fi
ok "虚拟环境就绪"

source .venv/bin/activate

# ====================
# 5. 安装依赖
# ====================
step=5
info "安装 Python 依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q || {
    err "pip install 失败，尝试使用清华镜像重试..."
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
}
ok "依赖安装完成"

# ====================
# 6. 构建知识库（延迟构建，仅首次）
# ====================
step=6
info "检查知识库..."
if [ ! -d "data/maoxuan/chroma_db" ] || [ ! -f "data/maoxuan/chroma_db/chroma.sqlite3" ] 2>/dev/null; then
    warn "首次运行，需要构建知识库（约30秒）..."
    python3 -c "
import sys, os
sys.path.insert(0, 'src')
os.chdir('${PROJECT_DIR}')

from core.cognitive_graph import CognitiveGraph
from core.maoxuan_retriever import MaoxuanRetriever

print('  构建认知图谱...')
graph = CognitiveGraph()
graph.load_builtin_data()
print(f'  ✓ 认知图谱: {len(graph.graph.nodes)} 节点, {len(graph.graph.edges)} 边')

print('  构建毛选向量索引...')
retriever = MaoxuanRetriever()
retriever.build_index()
print(f'  ✓ 毛选索引: {retriever.get_stats()[\"document_count\"]} 文档')
print('  ✓ 知识库就绪')
" || {
        err "知识库构建失败"
        exit 1
    }
else
    ok "知识库已存在"
fi

# ====================
# 7. 启动后端
# ====================
step=7
info "启动后端服务..."

# 检查端口是否被占用
if lsof -ti:8000 >/dev/null 2>&1; then
    warn "端口 8000 被占用，尝试释放..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# 加载 .env
set -a
source .env 2>/dev/null || true
set +a

export MODEL_NAME=${MODEL_NAME}
export OLLAMA_HOST=${OLLAMA_HOST:-http://localhost:11434}
export API_PORT=${API_PORT:-8000}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

ok "后端配置: model=${MODEL_NAME}, port=${API_PORT}"

# 启动后台服务
python src/api/start_server.py --host 0.0.0.0 --port ${API_PORT} &
BACKEND_PID=$!

# 等待后端启动
for i in {1..30}; do
    if curl -s http://localhost:${API_PORT}/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        err "后端进程已退出，请检查日志"
        exit 1
    fi
done

ok "后端启动成功: http://localhost:${API_PORT}"

# ====================
# 8. 打开浏览器
# ====================
step=8
info "打开浏览器..."

if command_exists open; then
    # macOS
    open "http://localhost:${API_PORT}/docs" 2>/dev/null || true
    open "frontend/simple.html" 2>/dev/null || true
elif command_exists xdg-open; then
    # Linux
    xdg-open "http://localhost:${API_PORT}/docs" 2>/dev/null || true
    xdg-open "frontend/simple.html" 2>/dev/null || true
else
    warn "无法自动打开浏览器，请手动访问:"
    echo "  API 文档:  http://localhost:${API_PORT}/docs"
    echo "  前端页面:  file://${PROJECT_DIR}/frontend/simple.html"
fi

# ====================
# 完成提示
# ====================
echo ""
echo "=========================================="
echo -e "  ${GREEN}教员AI顾问 已启动！${NC}"
echo "=========================================="
echo ""
echo "  API 文档:  http://localhost:${API_PORT}/docs"
echo "  前端:      file://${PROJECT_DIR}/frontend/simple.html"
echo ""
echo "  按 Ctrl+C 停止服务"
echo ""

# 保持脚本运行，等待 Ctrl+C
wait $BACKEND_PID
