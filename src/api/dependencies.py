"""
教员AI顾问 API - 依赖注入模块

提供FastAPI依赖函数，包括：
- 引擎单例管理（全局JiaoyuanEngine实例）
- 会话管理（获取会话历史、状态）
- Ollama健康检查
- 请求上下文

所有依赖函数均可用于FastAPI的Dependency Injection系统。

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import Depends

# 将core目录加入路径（支持从api目录和项目根目录运行）
_current_dir = os.path.dirname(os.path.abspath(__file__))
_core_dir = os.path.join(_current_dir, "..", "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

# 导入核心引擎
from engine import JiaoyuanEngine
from models import EngineConfig

# ============================================================================
# 日志配置
# ============================================================================

logger = logging.getLogger("jiaoyuan.api")


# ============================================================================
# 全局状态
# ============================================================================

class EngineManager:
    """
    引擎管理器 - 单例模式

    管理全局JiaoyuanEngine实例的生命周期：
    - 延迟初始化（首次请求时才创建）
    - 异步锁保护并发初始化
    - 优雅关闭支持
    """

    _instance: Optional[JiaoyuanEngine] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _initialized: bool = False
    _init_error: Optional[str] = None
    _start_time: float = 0.0

    @classmethod
    async def get_engine(cls) -> JiaoyuanEngine:
        """
        获取全局引擎实例（线程安全）

        首次调用时会初始化引擎，后续调用返回已创建的实例。
        使用异步锁保护并发初始化的竞态条件。

        Returns:
            JiaoyuanEngine实例

        Raises:
            RuntimeError: 引擎初始化失败
        """
        if cls._instance is not None:
            return cls._instance

        async with cls._lock:
            # 双重检查（在锁内再次检查）
            if cls._instance is not None:
                return cls._instance

            try:
                logger.info("Initializing JiaoyuanEngine...")
                cls._start_time = time.time()

                # 读取环境变量中的配置
                config = cls._load_config_from_env()

                # 创建引擎实例
                cls._instance = JiaoyuanEngine(config=config)
                cls._initialized = True

                elapsed = time.time() - cls._start_time
                logger.info(
                    "JiaoyuanEngine initialized in %.2fs (model=%s)",
                    elapsed,
                    config.model_name,
                )
                return cls._instance

            except Exception as e:
                cls._init_error = str(e)
                logger.exception("Failed to initialize JiaoyuanEngine: %s", e)
                raise RuntimeError(f"引擎初始化失败: {e}")

    @classmethod
    def _load_config_from_env(cls) -> EngineConfig:
        """
        从环境变量加载配置

        支持的环境变量：
        - OLLAMA_HOST: Ollama服务地址（默认 http://localhost:11434）
        - MODEL_NAME: 模型名称（默认 qwen3:8b）
        - LLM_TIMEOUT: LLM超时时间（默认 30秒）
        - MAX_FULL_TURNS: 最大完整轮次（默认 10）
        - ENABLE_THINKING: 启用思考模式（默认 true）

        Returns:
            EngineConfig实例
        """
        config_kwargs: Dict[str, Any] = {}

        if host := os.environ.get("OLLAMA_HOST"):
            config_kwargs["ollama_host"] = host

        if model := os.environ.get("MODEL_NAME"):
            config_kwargs["model_name"] = model

        if timeout := os.environ.get("LLM_TIMEOUT"):
            try:
                config_kwargs["llm_timeout_seconds"] = int(timeout)
            except ValueError:
                logger.warning("Invalid LLM_TIMEOUT value: %s", timeout)

        if turns := os.environ.get("MAX_FULL_TURNS"):
            try:
                config_kwargs["max_full_turns"] = int(turns)
            except ValueError:
                logger.warning("Invalid MAX_FULL_TURNS value: %s", turns)

        if thinking := os.environ.get("ENABLE_THINKING"):
            config_kwargs["enable_thinking_mode"] = thinking.lower() in ("true", "1", "yes")

        return EngineConfig(**config_kwargs) if config_kwargs else EngineConfig()

    @classmethod
    async def close(cls) -> None:
        """关闭引擎，释放资源"""
        if cls._instance is not None:
            try:
                await cls._instance.close()
                logger.info("JiaoyuanEngine closed")
            except Exception as e:
                logger.error("Error closing engine: %s", e)
            finally:
                cls._instance = None
                cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """检查引擎是否已初始化"""
        return cls._initialized and cls._instance is not None

    @classmethod
    def get_init_error(cls) -> Optional[str]:
        """获取初始化错误信息"""
        return cls._init_error

    @classmethod
    def get_uptime(cls) -> float:
        """获取运行时间（秒）"""
        if cls._start_time == 0:
            return 0.0
        return time.time() - cls._start_time


# ============================================================================
# FastAPI依赖函数
# ============================================================================

async def get_engine() -> JiaoyuanEngine:
    """
    FastAPI依赖：获取引擎实例

    用法:
        ```python
        @app.post("/api/chat")
        async def chat(request: ChatRequest, engine: JiaoyuanEngine = Depends(get_engine)):
            result = await engine.chat(request.message, request.session_id, request.user_id)
            return result
        ```

    Returns:
        JiaoyuanEngine实例
    """
    return await EngineManager.get_engine()


async def get_session_info(
    session_id: str,
    user_id: str = "anonymous",
    engine: JiaoyuanEngine = Depends(get_engine),  # type: ignore[misc]
) -> Dict[str, Any]:
    """
    FastAPI依赖：获取会话信息

    从引擎的会话管理器中提取指定会话的历史和状态。

    Args:
        session_id: 会话ID
        user_id: 用户ID
        engine: 引擎实例（自动注入）

    Returns:
        会话信息字典，包含历史、认知状态等
    """
    from api.models import DialogueTurnInfo

    session_key = f"{user_id}:{session_id}"

    # 检查会话是否存在
    if session_key not in engine._sessions:
        return {
            "exists": False,
            "session_id": session_id,
            "user_id": user_id,
            "total_turns": 0,
            "history": [],
            "cognitive_state": "",
        }

    memory = engine._sessions[session_key]
    context = memory.get_context()

    # 构建历史记录
    history = context.get("history", [])
    turns = []
    for h in history:
        turns.append(DialogueTurnInfo(
            user=h.get("user", ""),
            assistant=h.get("assistant", ""),
        ))

    return {
        "exists": True,
        "session_id": session_id,
        "user_id": user_id,
        "total_turns": len(turns),
        "history": turns,
        "cognitive_state": context.get("cognitive_state", ""),
        "user_profile": context.get("user_profile"),
        "cognitive_tracker": context.get("cognitive_tracker"),
    }


async def verify_ollama() -> Dict[str, Any]:
    """
    FastAPI依赖：检查Ollama服务健康状态

    用于需要确保LLM服务可用的端点。

    Returns:
        Ollama健康状态字典

    Raises:
        HTTPException: Ollama服务不可用
    """
    from fastapi import HTTPException

    try:
        engine = await EngineManager.get_engine()
        health = await engine.health_check()
        llm_status = health.get("llm", {})

        if not llm_status.get("healthy", False):
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Ollama LLM服务不可用",
                    "code": "OLLAMA_UNAVAILABLE",
                    "model": llm_status.get("model", "unknown"),
                },
            )

        return llm_status

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"健康检查失败: {str(e)}",
                "code": "HEALTH_CHECK_FAILED",
            },
        )


def get_request_id() -> str:
    """
    FastAPI依赖：生成请求追踪ID

    为每个请求生成唯一ID，便于日志追踪和错误排查。

    Returns:
        UUID字符串
    """
    return f"req_{uuid.uuid4().hex[:12]}"
