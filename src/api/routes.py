"""教员AI顾问 API - 路由模块

将所有API端点组织到独立的路由组：
- chat_routes: 对话相关（普通对话、流式对话）
- session_routes: 会话管理（获取历史、重置会话）
- admin_routes: 管理接口（健康检查、系统统计、WebSocket统计）

作者: AI系统架构师
版本: 3.0.1
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
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
    DialogueTurnInfo,
    FeedbackRequest,
    HealthCheckResponse,
    HealthStatus,
    ReasoningDetail,
    ReasoningResultInfo,
    SessionInfo,
    SessionResetResponse,
    SocraticQuestionInfo,
    SystemStatsResponse,
    UserIntentInfo,
    ProblemProfileInfo,
)
from api.dependencies import (
    EngineManager,
    get_engine,
)
from api.websocket_manager import websocket_manager

logger = logging.getLogger("jiaoyuan.api.routes")


def create_error_response(
    message: str,
    code: str = "INTERNAL_ERROR",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    request_id: Optional[str] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"message": message, "code": code},
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
        },
    )


chat_routes = APIRouter(prefix="/chat", tags=["对话"])


@chat_routes.post(
    "",
    response_model=ChatResponse,
    summary="普通对话",
    description="发送用户消息，获取AI的完整回复（含推理过程）。",
)
async def chat(
    request: ChatRequest,
    engine: JiaoyuanEngine = Depends(get_engine),
) -> ChatResponse:
    try:
        result = await engine.chat(
            request.message,
            request.session_id,
            request.user_id,
        )

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

    修复：不再在路由中重复 accept，由 websocket_manager.connect() 统一处理。
    """
    # 获取引擎
    try:
        engine = await EngineManager.get_engine()
    except Exception as e:
        await websocket.accept()  # 必须先 accept 才能发送错误
        await websocket_manager.send_error(
            websocket,
            f"引擎未就绪: {str(e)}",
            error_code="ENGINE_NOT_READY",
        )
        await websocket.close(code=1011, reason="Engine not ready")
        return

    # 等待第一条消息获取会话信息
    try:
        await websocket.accept()  # 首次 accept
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
                data = await websocket.receive_json()
                continue

            await websocket_manager.handle_chat_stream(
                websocket=websocket,
                session_id=session_id,
                user_id=user_id,
                message=message,
                engine=engine,
            )

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


@chat_routes.post("/feedback", summary="提交反馈")
async def submit_feedback(
    request: FeedbackRequest,
    engine: JiaoyuanEngine = Depends(get_engine),
) -> Dict[str, Any]:
    logger.info(
        "Feedback received: session=%s, turn=%d, rating=%d",
        request.session_id,
        request.turn_index,
        request.rating,
    )

    return {
        "success": True,
        "message": "反馈已提交，感谢你的帮助！",
        "session_id": request.session_id,
        "rating": request.rating,
    }


session_routes = APIRouter(prefix="/sessions", tags=["会话管理"])


@session_routes.get("/{session_id}", response_model=SessionInfo, summary="获取会话历史")
async def get_session(
    session_id: str,
    user_id: str = Query(default="anonymous", description="用户ID"),
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SessionInfo:
    session_key = f"{user_id}:{session_id}"

    if session_key not in engine._sessions:
        return SessionInfo(
            session_id=session_id,
            user_id=user_id,
            total_turns=0,
            history=[],
            cognitive_state="会话尚未开始",
        )

    memory = engine._sessions[session_key]
    context = memory.get_context()

    raw_history = context.get("history", [])
    history = [
        DialogueTurnInfo(
            user=h.get("user", ""),
            assistant=h.get("assistant", ""),
        )
        for h in raw_history
    ]

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


@session_routes.delete("/{session_id}", response_model=SessionResetResponse, summary="重置会话")
async def reset_session(
    session_id: str,
    user_id: str = Query(default="anonymous", description="用户ID"),
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SessionResetResponse:
    session_key = f"{user_id}:{session_id}"

    if session_key not in engine._sessions:
        return SessionResetResponse(
            session_id=session_id,
            message=f"会话 '{session_id}' 不存在，无需重置",
            previous_turns=0,
        )

    memory = engine._sessions[session_key]
    previous_turns = len(memory.dialogue_memory.turns)

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


@session_routes.get("", summary="列出会话")
async def list_sessions(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> Dict[str, Any]:
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


admin_routes = APIRouter(prefix="", tags=["系统管理"])


@admin_routes.get("/health", response_model=HealthCheckResponse, summary="健康检查")
async def health_check(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> HealthCheckResponse:
    try:
        engine_health = await engine.health_check()

        llm_status = engine_health.get("llm", {})
        llm_healthy = llm_status.get("healthy", False)

        status = HealthStatus.HEALTHY if llm_healthy else HealthStatus.DEGRADED

        return HealthCheckResponse(
            status=status,
            version="3.0.1",
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
            version="3.0.1",
            model="unknown",
            timestamp=datetime.now().isoformat(),
            components={},
            active_sessions=0,
        )


@admin_routes.get("/stats", response_model=SystemStatsResponse, summary="系统统计")
async def get_stats(
    engine: JiaoyuanEngine = Depends(get_engine),
) -> SystemStatsResponse:
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


@admin_routes.get("/ws-stats", summary="WebSocket统计")
async def get_websocket_stats() -> Dict[str, Any]:
    stats = websocket_manager.get_stats()
    return {
        **stats,
        "is_closed": websocket_manager.is_closed,
    }


@admin_routes.post("/cleanup", summary="清理资源")
async def cleanup_resources(
    max_idle_seconds: float = Query(default=3600.0, ge=60.0, description="最大空闲时间(秒)"),
) -> Dict[str, Any]:
    cleaned_connections = await websocket_manager.cleanup_idle_connections(max_idle_seconds)

    return {
        "success": True,
        "cleaned_connections": cleaned_connections,
        "remaining_connections": websocket_manager.connection_count,
        "timestamp": datetime.now().isoformat(),
    }
