"""
教员AI顾问 API - 路由模块

将所有API端点组织到独立的路由组：
- chat_routes: 对话相关（普通对话、流式对话）
- session_routes: 会话管理（获取历史、重置会话）
- admin_routes: 管理接口（健康检查、系统统计、WebSocket统计）

所有路由使用FastAPI的APIRouter，支持：
- 自动API文档生成
- 请求/响应模型验证
- 依赖注入
- 统一的错误处理

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import logging
import time
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse

# 确保core模块可导入
_current_dir = os.path.dirname(os.path.abspath(__file__))
_core_dir = os.path.join(_current_dir, "..", "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from engine import JiaoyuanEngine

from api.models import (
    APIErrorResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    DialogueTurnInfo,
    FeedbackRequest,
    HealthCheckResponse,
    HealthStatus,
    ReasoningDetail,
    ReasoningResultInfo,
    SessionInfo,
    SessionListResponse,
    SessionResetResponse,
    SocraticQuestionInfo,
    StreamChunk,
    SystemStatsResponse,
    UserIntentInfo,
    ProblemProfileInfo,
    WebSocketMessage,
)
from api.dependencies import (
    EngineManager,
    get_engine,
    get_request_id,
    get_session_info,
)
from api.websocket_manager import websocket_manager

logger = logging.getLogger("jiaoyuan.api.routes")

# ============================================================================
# 错误处理工具
# ============================================================================

def create_error_response(
    message: str,
    code: str = "INTERNAL_ERROR",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """
    创建统一的错误响应

    Args:
        message: 错误消息
        code: 错误代码
        status_code: HTTP状态码
        request_id: 请求追踪ID

    Returns:
        JSONResponse错误响应
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"message": message, "code": code},
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
        },
    )


# ============================================================================
# 对话路由
# ============================================================================

chat_routes = APIRouter(prefix="/chat", tags=["对话"])


@chat_routes.post(
    "",
    response_model=ChatResponse,
    summary="普通对话",
    description="发送用户消息，获取AI的完整回复（含推理过程）。",
    responses={
        200: {"description": "成功", "model": ChatResponse},
        422: {"description": "请求数据验证失败"},
        500: {"description": "服务器内部错误", "model": APIErrorResponse},
        503: {"description": "LLM服务不可用", "model": APIErrorResponse},
    },
)
async def chat(
    request: ChatRequest,
    engine: JiaoyuanEngine = Depends(get_engine),
) -> ChatResponse:
    """
    普通对话接口

    接收用户消息，通过五层认知架构处理后返回完整响应。
    包含最终回复、推理过程和性能计时。

    - **message**: 用户输入消息（1-10000字符）
    - **session_id**: 会话ID（默认"default"）
    - **user_id**: 用户ID（默认"anonymous"）
    """
    try:
        result = await engine.chat(
            request.message,
            request.session_id,
            request.user_id,
        )

        # 构造推理详情
        user_intent = UserIntentInfo(
            topic=result.get("user_intent", {}).get("topic", ""),
            emotion=result.get("user_intent", {}).get("emotion", ""),
            cognitive_stage=result.get("user_intent", {}).get("cognitive_stage", ""),
            keywords=result.get("user_intent", {}).get("keywords", []),
        )

        problem_profile = ProblemProfileInfo(
            type=result.get("problem_profile", {}).get("type", ""),
            framework=result.get("problem_profile", {}).get("framework", ""),
        )

        socratic_questions = [
            SocraticQuestionInfo(q=q.get("q", ""), type=q.get("type", ""))
            for q in result.get("reasoning_result", {}).get("socratic_questions", [])
        ]

        reasoning_result = ReasoningResultInfo(
            key_insights=result.get("reasoning_result", {}).get("key_insights", []),
            socratic_questions=socratic_questions,
            reasoning_time_ms=result.get("reasoning_result", {}).get("reasoning_time_ms", 0),
        )

        reasoning = ReasoningDetail(
            thinking_content=result.get("thinking", ""),
            user_intent=user_intent,
            problem_profile=problem_profile,
            reasoning_result=reasoning_result,
            layer_timings=result.get("layer_timings", {}),
        )

        return ChatResponse(
            response=result.get("response", ""),
            reasoning=reasoning,
            timing={
                "total_ms": result.get("processing_time_ms", 0),
                **{f"{k}_ms": v for k, v in result.get("layer_timings", {}).items()},
            },
            session_id=request.session_id,
            error=result.get("error"),
        )

    except Exception as e:
        logger.exception("Chat endpoint error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"对话处理失败: {str(e)}", "code": "CHAT_ERROR"},
        )


@chat_routes.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    """
    WebSocket流式对话接口

    通过WebSocket提供实时流式对话能力。

    连接后，客户端发送JSON消息：
    ```json
    {"message": "你好", "session_id": "s1", "user_id": "u1"}
    ```

    服务器返回流式响应块：
    - `{"type": "status", "content": "感知分析中..."}`
    - `{"type": "thinking", "content": "推理过程..."}`
    - `{"type": "content", "content": "回复片段..."}`
    - `{"type": "done", "content": "", "processing_time_ms": 2500}`

    错误时返回：
    - `{"type": "error", "content": "错误描述", "code": "ERROR_CODE"}`
    """
    # 首次连接时不接受（等待第一条消息获取session_id）
    await websocket.accept()

    # 获取引擎
    try:
        engine = await EngineManager.get_engine()
    except Exception as e:
        await websocket_manager.send_error(
            websocket,
            f"引擎未就绪: {str(e)}",
            error_code="ENGINE_NOT_READY",
        )
        await websocket.close(code=1011, reason="Engine not ready")
        return

    # 等待第一条消息获取会话信息
    try:
        data = await websocket.receive_json()
        session_id = data.get("session_id", "default")
        user_id = data.get("user_id", "anonymous")
    except Exception:
        await websocket.close(code=1003, reason="Invalid initial message")
        return

    # 注册连接
    await websocket_manager.connect(websocket, session_id=session_id, user_id=user_id)

    try:
        while True:
            message = data.get("message", "").strip()

            if not message:
                await websocket_manager.send_error(
                    websocket,
                    "消息不能为空",
                    error_code="EMPTY_MESSAGE",
                )
                # 等待下一条消息
                data = await websocket.receive_json()
                continue

            # 处理流式对话
            await websocket_manager.handle_chat_stream(
                websocket=websocket,
                session_id=session_id,
                user_id=user_id,
                message=message,
                engine=engine,
            )

            # 等待下一条消息
            data = await websocket.receive_json()

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        await websocket_manager.send_error(
            websocket,
            f"WebSocket错误: {str(e)}",
            error_code="WEBSOCKET_ERROR",
        )
    finally:
        await websocket_manager.disconnect(websocket, session_id=session_id)


@chat_routes.post(
    "/feedback",
    summary="提交反馈",
    description="提交对AI回复的反馈，帮助改进系统。",
    responses={
        200: {"description": "反馈提交成功"},
        422: {"description": "请求数据验证失败"},
    },
)
async def submit_feedback(
    request: FeedbackRequest,
    engine: JiaoyuanEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    提交用户反馈

    - **session_id**: 会话ID
    - **turn_index**: 对话轮次索引（-1表示最后一轮）
    - **rating**: 评分 1-5
    - **comment**: 反馈文字（可选）
    """
    # TODO: 将反馈持久化到文件或数据库
    logger.info(
        "Feedback received: session=%s, turn=%d, rating=%d, comment='%s'",
        request.session_id,
        request.turn_index,
        request.rating,
        request.comment[:50] if request.comment else "",
    )

    return {
        "success": True,
        "message": "反馈已提交，感谢你的帮助！",
        "session_id": request.session_id,
        "rating": request.rating,
    }


# ============================================================================
# 会话路由
# ============================================================================

session_routes = APIRouter(prefix="/sessions", tags=["会话管理"])


@session_routes.get(
    "/{session_id}",
    response_model=SessionInfo,
    summary="获取会话历史",
    description="获取指定会话的对话历史和认知状态。",
    responses={
        200: {"description": "成功", "model": SessionInfo},
        404: {"description": "会话不存在", "model": APIErrorResponse},
    },
)
async def get_session(
    session_id: str,
    user_id: str = Query(default="anonymous", description="用户ID"),
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SessionInfo:
    """
    获取会话历史

    - **session_id**: 会话ID（路径参数）
    - **user_id**: 用户ID（查询参数，默认"anonymous"）
    """
    session_key = f"{user_id}:{session_id}"

    if session_key not in engine._sessions:
        # 会话不存在，返回空会话
        return SessionInfo(
            session_id=session_id,
            user_id=user_id,
            total_turns=0,
            history=[],
            cognitive_state="会话尚未开始",
        )

    memory = engine._sessions[session_key]
    context = memory.get_context()

    # 构建对话历史
    raw_history = context.get("history", [])
    history = [
        DialogueTurnInfo(
            user=h.get("user", ""),
            assistant=h.get("assistant", ""),
        )
        for h in raw_history
    ]

    # 获取用户画像摘要
    user_profile = context.get("user_profile")
    profile_summary = {}
    if user_profile:
        profile_summary = {
            "decision_style": getattr(user_profile, "decision_style", "unknown"),
            "total_dialogues": getattr(user_profile, "total_dialogues", 0),
            "total_turns": getattr(user_profile, "total_turns", 0),
        }

    return SessionInfo(
        session_id=session_id,
        user_id=user_id,
        total_turns=len(history),
        history=history,
        cognitive_state=context.get("cognitive_state", ""),
        profile_summary=profile_summary,
    )


@session_routes.delete(
    "/{session_id}",
    response_model=SessionResetResponse,
    summary="重置会话",
    description="清除指定会话的对话历史，重置认知状态。",
    responses={
        200: {"description": "会话已重置", "model": SessionResetResponse},
    },
)
async def reset_session(
    session_id: str,
    user_id: str = Query(default="anonymous", description="用户ID"),
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SessionResetResponse:
    """
    重置会话

    清除指定会话的所有对话历史、认知追踪器和记忆状态。

    - **session_id**: 会话ID（路径参数）
    - **user_id**: 用户ID（查询参数，默认"anonymous"）
    """
    session_key = f"{user_id}:{session_id}"

    if session_key not in engine._sessions:
        return SessionResetResponse(
            session_id=session_id,
            message=f"会话 '{session_id}' 不存在，无需重置",
            previous_turns=0,
        )

    # 获取重置前的信息
    memory = engine._sessions[session_key]
    previous_turns = len(memory.dialogue_memory.turns)

    # 从引擎中删除会话（下次会自动创建新的）
    del engine._sessions[session_key]

    logger.info(
        "Session reset: session=%s, user=%s, previous_turns=%d",
        session_id,
        user_id,
        previous_turns,
    )

    return SessionResetResponse(
        session_id=session_id,
        message=f"会话 '{session_id}' 已重置，可以开始新的对话",
        previous_turns=previous_turns,
    )


@session_routes.get(
    "",
    summary="列出会话",
    description="列出所有活跃会话（开发调试用途）。",
)
async def list_sessions(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> Dict[str, Any]:
    """
    列出所有活跃会话

    返回当前内存中的所有会话信息。
    """
    sessions = []
    for key, memory in engine._sessions.items():
        parts = key.split(":", 1)
        user_id = parts[0] if parts else "unknown"
        session_id = parts[1] if len(parts) > 1 else key

        stats = memory.get_stats()
        sessions.append({
            "session_id": session_id,
            "user_id": user_id,
            "turns": stats.get("dialogue", {}).get("total_turns", 0),
            "cognitive_stage": stats.get("cognitive", {}).get("current_stage", ""),
            "loop_count": stats.get("cognitive", {}).get("loop_count", 0),
        })

    return {
        "total": len(sessions),
        "sessions": sessions,
    }


# ============================================================================
# 管理路由
# ============================================================================

admin_routes = APIRouter(prefix="", tags=["系统管理"])


@admin_routes.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="健康检查",
    description="检查API和各组件的健康状态。",
)
async def health_check(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> HealthCheckResponse:
    """
    健康检查

    返回API和各组件的健康状态：
    - LLM服务（Ollama）
    - 认知图谱
    - 毛选检索器
    - 活跃会话数
    """
    try:
        engine_health = await engine.health_check()

        llm_status = engine_health.get("llm", {})
        llm_healthy = llm_status.get("healthy", False)

        status = HealthStatus.HEALTHY if llm_healthy else HealthStatus.DEGRADED

        return HealthCheckResponse(
            status=status,
            version="3.0.0",
            model=llm_status.get("model", "qwen3:8b"),
            timestamp=datetime.now().isoformat(),
            components={
                "llm": llm_status,
                "cognitive_graph": engine_health.get("cognitive_graph", {}),
                "maoxuan": engine_health.get("maoxuan", {}),
            },
            active_sessions=engine_health.get("sessions", 0),
        )

    except Exception as e:
        logger.exception("Health check failed: %s", e)
        return HealthCheckResponse(
            status=HealthStatus.UNHEALTHY,
            version="3.0.0",
            model="unknown",
            timestamp=datetime.now().isoformat(),
            components={},
            active_sessions=0,
        )


@admin_routes.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="系统统计",
    description="获取引擎运行状态和统计数据。",
)
async def get_stats(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SystemStatsResponse:
    """
    系统统计

    返回引擎配置、会话统计、认知图谱和毛选库的统计信息。
    """
    try:
        engine_stats = engine.get_stats()

        return SystemStatsResponse(
            config=engine_stats.get("config", {}),
            sessions={
                "active": engine_stats.get("sessions", 0),
                "total_sessions": len(engine._sessions),
            },
            cognitive_graph=engine_stats.get("cognitive_graph", {}),
            maoxuan=engine_stats.get("maoxuan", {}),
            uptime_seconds=EngineManager.get_uptime(),
        )

    except Exception as e:
        logger.exception("Stats endpoint error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"获取统计失败: {str(e)}", "code": "STATS_ERROR"},
        )


@admin_routes.get(
    "/ws-stats",
    summary="WebSocket统计",
    description="获取WebSocket连接统计信息（开发调试用途）。",
)
async def get_websocket_stats() -> Dict[str, Any]:
    """
    WebSocket连接统计

    返回当前WebSocket连接数、会话数和连接详情。
    """
    stats = websocket_manager.get_stats()
    return {
        **stats,
        "is_closed": websocket_manager.is_closed,
    }


@admin_routes.post(
    "/cleanup",
    summary="清理资源",
    description="清理空闲连接和过期会话（管理用途）。",
)
async def cleanup_resources(
    max_idle_seconds: float = Query(default=3600.0, ge=60.0, description="最大空闲时间(秒)"),
) -> Dict[str, Any]:
    """
    清理资源

    - **max_idle_seconds**: 最大空闲时间（秒，默认3600）
    """
    cleaned_connections = await websocket_manager.cleanup_idle_connections(max_idle_seconds)

    return {
        "success": True,
        "cleaned_connections": cleaned_connections,
        "remaining_connections": websocket_manager.connection_count,
        "timestamp": datetime.now().isoformat(),
    }
