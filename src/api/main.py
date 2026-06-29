"""教员AI顾问 API - FastAPI主应用

五层认知架构的教员AI顾问Web后端入口。

提供：
- RESTful API（对话、会话管理、系统监控）
- WebSocket实时流式对话
- 自动API文档（/docs 和 /redoc）
- CORS跨域支持
- 统一错误处理
- 请求日志记录
- 优雅关闭

启动方式:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

环境变量:
    OLLAMA_HOST: Ollama服务地址（默认 http://localhost:11434）
    MODEL_NAME: 模型名称（默认 qwen3:8b）
    API_HOST: API绑定地址（默认 0.0.0.0）
    API_PORT: API端口（默认 8000）
    LOG_LEVEL: 日志级别（默认 INFO）

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

# ============================================================================
# 路径设置（确保core和api模块可导入）
# ============================================================================

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.join(_current_dir, "..")
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

# ============================================================================
# 加载环境变量（确保 .env 配置生效）
# ============================================================================

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv 未安装，依赖系统环境变量

# ============================================================================
# FastAPI导入
# ============================================================================

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.dependencies import EngineManager
from api.models import APIErrorResponse
from api.routes import chat_routes, session_routes, admin_routes
from api.websocket_manager import websocket_manager

# ============================================================================
# 日志配置
# ============================================================================

def setup_logging(log_level: str = "INFO") -> None:
    """
    配置日志系统

    Args:
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# 从环境变量读取日志级别
setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("jiaoyuan.api")

# ============================================================================
# 应用生命周期
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI应用生命周期管理

    启动时：
    - 初始化日志系统
    - 预初始化引擎（可选）

    关闭时：
    - 关闭所有WebSocket连接
    - 释放引擎资源
    - 清理临时数据
    """
    # ========== 启动 ==========
    logger.info("=" * 60)
    logger.info("教员AI顾问 API 正在启动...")
    logger.info("=" * 60)

    start_time = time.time()

    # 预初始化引擎（提前加载，避免首个请求等待）
    try:
        logger.info("正在预初始化引擎...")
        await EngineManager.get_engine()
        elapsed = time.time() - start_time
        logger.info("引擎预初始化完成 (%.2fs)", elapsed)
    except Exception as e:
        logger.warning("引擎预初始化失败: %s", e)
        logger.warning("将在首个请求时重试初始化")

    logger.info("API服务就绪 - 文档地址: http://localhost:%s/docs", os.environ.get("API_PORT", "8000"))
    logger.info("=" * 60)

    yield  # 应用运行期间

    # ========== 关闭 ==========
    logger.info("教员AI顾问 API 正在关闭...")

    # 关闭所有WebSocket连接
    try:
        await websocket_manager.close_all()
    except Exception as e:
        logger.error("关闭WebSocket连接时出错: %s", e)

    # 关闭引擎
    try:
        await EngineManager.close()
    except Exception as e:
        logger.error("关闭引擎时出错: %s", e)

    logger.info("教员AI顾问 API 已关闭")


# ============================================================================
# FastAPI应用实例
# ============================================================================

app = FastAPI(
    title="教员AI顾问 API",
    description="""
    五层认知架构的教员AI顾问 - RESTful API & WebSocket

    ## 核心能力

    - **普通对话** (`POST /api/chat`): 发送消息获取完整回复
    - **流式对话** (`WebSocket /api/chat/ws`): 实时流式交互
    - **会话管理**: 查看历史、重置会话
    - **系统监控**: 健康检查、性能统计

    ## 五层认知架构

    1. 感知层 (Perception): 语义解析 + 情感探测 + 意图分类
    2. 理解层 (Understanding): 问题建模 + 知识检索
    3. 推理层 (Reasoning): 苏格拉底提问 + 矛盾分析 + 阶段评估
    4. 记忆层 (Memory): 对话历史 + 用户画像 + 认知追踪
    5. 表达层 (Expression): 教员风格回复生成

    ## 认证

    当前版本不强制认证。生产环境建议添加API Key或JWT认证。
    """,
    version="3.0.0",
    contact={
        "name": "AI系统架构师",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# 中间件配置
# ============================================================================

# CORS配置（允许前端开发服务器访问）
# 生产环境应收紧允许的来源
cors_origins_str = os.environ.get("CORS_ORIGINS", "")
if cors_origins_str:
    _allow_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
else:
    _allow_origins = [
        "http://localhost:3000",     # React开发服务器
        "http://localhost:5173",     # Vite开发服务器
        "http://localhost:8080",     # 通用前端开发服务器
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
    expose_headers=["X-Request-ID", "X-Process-Time"],  # 暴露的响应头
    max_age=600,  # CORS预检缓存时间（秒）
)

# Gzip压缩（提高传输效率）
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ============================================================================
# 自定义中间件
# ============================================================================

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    请求计时中间件

    为每个请求添加：
    - X-Process-Time: 处理时间（毫秒）
    - X-Request-ID: 请求追踪ID
    """
    start_time = time.time()
    request_id = f"req_{os.urandom(6).hex()}"

    # 将request_id附加到请求状态
    request.state.request_id = request_id

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{process_time:.2f}"
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    请求日志中间件

    记录每个请求的方法、路径、状态码和处理时间。
    """
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    logger.debug(
        "%s %s - %d - %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )

    return response


# ============================================================================
# 异常处理
# ============================================================================

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器

    捕获所有未处理的异常，返回统一格式的错误响应。
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.exception(
        "Unhandled exception: %s %s - %s",
        request.method,
        request.url.path,
        exc,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "message": "服务器内部错误，请稍后重试",
                "code": "INTERNAL_ERROR",
            },
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    ValueError处理器

    处理数据验证等ValueError异常。
    """
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "message": str(exc),
                "code": "VALIDATION_ERROR",
            },
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
        },
    )


# ============================================================================
# 路由注册
# ============================================================================

# 注册所有路由组
app.include_router(chat_routes, prefix="/api")
app.include_router(session_routes, prefix="/api")
app.include_router(admin_routes, prefix="/api")


# ============================================================================
# 根端点
# ============================================================================

@app.get(
    "/",
    summary="API根路径",
    description="返回API基本信息和可用端点列表。",
    tags=["根路径"],
)
async def root() -> Dict[str, Any]:
    """
    API根路径

    返回基本信息和文档链接。
    """
    return {
        "name": "教员AI顾问 API",
        "version": "3.0.0",
        "description": "五层认知架构的教员AI顾问",
        "model": "qwen3:8b",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/api/health",
    }


@app.get(
    "/api",
    summary="API信息",
    description="返回所有可用API端点列表。",
    tags=["根路径"],
)
async def api_info() -> Dict[str, Any]:
    """
    API信息

    返回所有可用端点和WebSocket路径。
    """
    return {
        "version": "3.0.0",
        "endpoints": {
            "chat": {
                "method": "POST",
                "path": "/api/chat",
                "description": "普通对话",
            },
            "chat_stream": {
                "method": "WebSocket",
                "path": "/api/chat/ws",
                "description": "流式对话",
            },
            "feedback": {
                "method": "POST",
                "path": "/api/chat/feedback",
                "description": "提交反馈",
            },
            "session": {
                "method": "GET",
                "path": "/api/sessions/{session_id}",
                "description": "获取会话历史",
            },
            "reset_session": {
                "method": "DELETE",
                "path": "/api/sessions/{session_id}",
                "description": "重置会话",
            },
            "list_sessions": {
                "method": "GET",
                "path": "/api/sessions",
                "description": "列出活跃会话",
            },
            "health": {
                "method": "GET",
                "path": "/api/health",
                "description": "健康检查",
            },
            "stats": {
                "method": "GET",
                "path": "/api/stats",
                "description": "系统统计",
            },
        },
    }


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    reload_mode = os.environ.get("API_RELOAD", "false").lower() == "true"

    logger.info("Starting uvicorn server: %s:%d (reload=%s)", host, port, reload_mode)

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload_mode,
        log_level="warning",
        access_log=False,
    )
