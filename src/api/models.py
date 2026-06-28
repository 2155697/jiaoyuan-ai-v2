"""
教员AI顾问 API - 数据模型定义

定义所有API请求/响应的Pydantic模型，确保类型安全、数据验证和自动文档生成。

所有模型继承自 pydantic.BaseModel，支持：
- 自动类型验证和转换
- JSON序列化/反序列化
- FastAPI自动文档生成
- 输入数据校验

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 枚举定义
# ============================================================================

class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class StreamChunkType(str, Enum):
    """流式输出块类型枚举"""
    THINKING = "thinking"       # 推理过程
    STATUS = "status"           # 状态更新
    CONTENT = "content"         # 回复内容
    DONE = "done"              # 完成信号
    ERROR = "error"            # 错误


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ============================================================================
# 请求模型
# ============================================================================

class ChatRequest(BaseModel):
    """
    普通对话请求

    用于 POST /api/chat 端点，发送用户消息并获取完整响应。

    示例:
        ```json
        {
            "message": "我想创业但不知道做什么",
            "session_id": "session_123",
            "user_id": "user_456"
        }
        ```
    """
    message: str = Field(
        ...,  # required
        min_length=1,
        max_length=10000,
        description="用户输入消息（1-10000字符）",
        examples=["我想创业但不知道做什么"],
    )
    session_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        description="会话ID，用于区分不同对话会话",
        examples=["session_123"],
    )
    user_id: str = Field(
        default="anonymous",
        min_length=1,
        max_length=128,
        description="用户ID，用于用户画像和持久化",
        examples=["user_456"],
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """去除消息首尾空白"""
        return v.strip()


class ChatStreamRequest(BaseModel):
    """
    流式对话请求

    用于 WebSocket /api/chat/ws 端点，支持实时流式响应。

    示例:
        ```json
        {
            "message": "我现在很迷茫",
            "session_id": "session_123",
            "user_id": "user_456"
        }
        ```
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户输入消息（1-10000字符）",
    )
    session_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        description="会话ID",
    )
    user_id: str = Field(
        default="anonymous",
        min_length=1,
        max_length=128,
        description="用户ID",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """去除消息首尾空白"""
        return v.strip()


class FeedbackRequest(BaseModel):
    """
    用户反馈请求

    用于提交对AI回复的反馈，帮助改进系统。

    示例:
        ```json
        {
            "session_id": "session_123",
            "turn_index": 0,
            "rating": 5,
            "comment": "很有帮助"
        }
        ```
    """
    session_id: str = Field(..., description="会话ID")
    turn_index: int = Field(default=-1, ge=-1, description="对话轮次索引，-1表示最后一轮")
    rating: int = Field(..., ge=1, le=5, description="评分 1-5")
    comment: str = Field(default="", max_length=1000, description="反馈文字")


# ============================================================================
# 响应模型
# ============================================================================

class UserIntentInfo(BaseModel):
    """感知层输出 - 用户意图信息"""
    topic: str = Field(default="", description="核心主题")
    emotion: str = Field(default="", description="主导情绪")
    cognitive_stage: str = Field(default="", description="认知阶段")
    keywords: List[str] = Field(default_factory=list, description="关键词")


class ProblemProfileInfo(BaseModel):
    """理解层输出 - 问题画像信息"""
    type: str = Field(default="", description="问题类型")
    framework: str = Field(default="", description="思维框架")


class SocraticQuestionInfo(BaseModel):
    """苏格拉底提问信息"""
    q: str = Field(default="", description="问题文本")
    type: str = Field(default="", description="问题类型")


class ReasoningResultInfo(BaseModel):
    """推理层输出 - 推理结果信息"""
    key_insights: List[str] = Field(default_factory=list, description="关键洞察")
    socratic_questions: List[SocraticQuestionInfo] = Field(default_factory=list, description="苏格拉底提问")
    reasoning_time_ms: int = Field(default=0, description="推理耗时(ms)")


class ReasoningDetail(BaseModel):
    """
    完整推理过程详情

    展示给用户查看引擎的推理过程。
    """
    thinking_content: str = Field(default="", description="引擎内部思考过程")
    user_intent: UserIntentInfo = Field(default_factory=UserIntentInfo, description="感知层分析")
    problem_profile: ProblemProfileInfo = Field(default_factory=ProblemProfileInfo, description="理解层分析")
    reasoning_result: ReasoningResultInfo = Field(default_factory=ReasoningResultInfo, description="推理层结果")
    layer_timings: Dict[str, int] = Field(default_factory=dict, description="各层耗时(ms)")


class ChatResponse(BaseModel):
    """
    普通对话响应

    POST /api/chat 端点的完整响应，包含最终回复和推理详情。

    示例:
        ```json
        {
            "response": "同志，你的迷茫我很理解...",
            "reasoning": {
                "thinking_content": "用户在创业方面感到迷茫...",
                "user_intent": {"topic": "创业迷茫", "emotion": "confused", ...},
                "problem_profile": {"type": "strategy_selection", ...},
                "reasoning_result": {"key_insights": [...], ...},
                "layer_timings": {"perception": 200, "understanding": 300, ...}
            },
            "timing": {
                "total_ms": 2500,
                "perception_ms": 200,
                "understanding_ms": 300,
                "reasoning_ms": 1500,
                "expression_ms": 500
            },
            "session_id": "session_123"
        }
        ```
    """
    response: str = Field(description="AI最终回复文本")
    reasoning: ReasoningDetail = Field(default_factory=ReasoningDetail, description="推理过程详情")
    timing: Dict[str, Any] = Field(default_factory=dict, description="性能计时信息")
    session_id: str = Field(default="", description="会话ID")
    error: Optional[str] = Field(default=None, description="错误信息（如有）")


class StreamChunk(BaseModel):
    """
    流式输出块

    WebSocket /api/chat/ws 端点返回的流式数据块。

    示例（thinking）:
        ```json
        {"type": "thinking", "content": "用户在创业方面感到迷茫..."}
        ```

    示例（content）:
        ```json
        {"type": "content", "content": "同志，你的迷茫"}
        ```

    示例（done）:
        ```json
        {"type": "done", "content": "", "processing_time_ms": 2500}
        ```
    """
    type: StreamChunkType = Field(description="块类型: thinking/status/content/done/error")
    content: str = Field(default="", description="内容文本")
    processing_time_ms: Optional[int] = Field(default=None, description="总处理时间（仅done类型）")


# ============================================================================
# 会话相关模型
# ============================================================================

class DialogueTurnInfo(BaseModel):
    """单轮对话信息"""
    user: str = Field(description="用户输入")
    assistant: str = Field(description="AI回复")
    timestamp: Optional[float] = Field(default=None, description="时间戳")


class SessionInfo(BaseModel):
    """
    会话信息

    GET /api/sessions/{id} 端点的响应。

    示例:
        ```json
        {
            "session_id": "session_123",
            "user_id": "user_456",
            "total_turns": 5,
            "history": [
                {"user": "你好", "assistant": "同志你好！..."},
                ...
            ],
            "cognitive_state": "第1轮循环，已完成2/6个阶段，当前聚焦：plan",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00"
        }
        ```
    """
    session_id: str = Field(description="会话ID")
    user_id: str = Field(description="用户ID")
    total_turns: int = Field(default=0, description="总对话轮次")
    history: List[DialogueTurnInfo] = Field(default_factory=list, description="对话历史")
    cognitive_state: str = Field(default="", description="认知状态摘要")
    profile_summary: Dict[str, Any] = Field(default_factory=dict, description="用户画像摘要")
    created_at: str = Field(default="", description="会话创建时间")
    updated_at: str = Field(default="", description="最后更新时间")


class SessionResetResponse(BaseModel):
    """会话重置响应"""
    session_id: str = Field(description="会话ID")
    message: str = Field(description="操作结果消息")
    previous_turns: int = Field(default=0, description="重置前的对话轮次")


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[SessionInfo] = Field(default_factory=list, description="会话列表")
    total: int = Field(default=0, description="总会话数")


# ============================================================================
# 系统状态模型
# ============================================================================

class HealthCheckResponse(BaseModel):
    """
    健康检查响应

    GET /api/health 端点的响应。

    示例:
        ```json
        {
            "status": "healthy",
            "version": "3.0.0",
            "model": "qwen3:8b",
            "timestamp": "2024-01-01T00:00:00",
            "components": {
                "llm": {"healthy": true, "model": "qwen3:8b"},
                "cognitive_graph": {"entities": 100, "relations": 200},
                "maoxuan": {"documents": 50}
            }
        }
        ```
    """
    status: HealthStatus = Field(description="整体健康状态")
    version: str = Field(default="3.0.0", description="API版本")
    model: str = Field(default="qwen3:8b", description="当前模型")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="检查时间")
    components: Dict[str, Any] = Field(default_factory=dict, description="各组件状态")
    active_sessions: int = Field(default=0, description="活跃会话数")


class SystemStatsResponse(BaseModel):
    """
    系统统计响应

    GET /api/stats 端点的响应，展示引擎运行状态。

    示例:
        ```json
        {
            "config": {
                "model": "qwen3:8b",
                "thinking_mode": true,
                "max_context": 8192
            },
            "sessions": {
                "active": 5,
                "total_sessions": 10
            },
            "cognitive_graph": {
                "entities": 150,
                "relations": 300
            },
            "maoxuan": {
                "documents": 50
            },
            "uptime_seconds": 3600
        }
        ```
    """
    config: Dict[str, Any] = Field(default_factory=dict, description="引擎配置")
    sessions: Dict[str, Any] = Field(default_factory=dict, description="会话统计")
    cognitive_graph: Dict[str, Any] = Field(default_factory=dict, description="认知图谱统计")
    maoxuan: Dict[str, Any] = Field(default_factory=dict, description="毛选库统计")
    uptime_seconds: float = Field(default=0.0, description="运行时间(秒)")


# ============================================================================
# 错误响应模型
# ============================================================================

class APIErrorDetail(BaseModel):
    """API错误详情"""
    field: Optional[str] = Field(default=None, description="出错的字段")
    message: str = Field(description="错误描述")
    code: str = Field(default="UNKNOWN_ERROR", description="错误代码")


class APIErrorResponse(BaseModel):
    """
    统一API错误响应

    所有错误均使用此格式返回，确保前端可以统一处理。

    示例:
        ```json
        {
            "success": false,
            "error": {
                "message": "输入消息不能为空",
                "code": "INVALID_INPUT"
            },
            "timestamp": "2024-01-01T00:00:00",
            "request_id": "req_123"
        }
        ```
    """
    success: bool = Field(default=False, description="是否成功")
    error: APIErrorDetail = Field(description="错误详情")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="错误时间")
    request_id: Optional[str] = Field(default=None, description="请求追踪ID")


class ValidationErrorResponse(APIErrorResponse):
    """
    数据验证错误响应

    当请求数据验证失败时返回，包含具体字段错误。

    示例:
        ```json
        {
            "success": false,
            "error": {
                "message": "请求数据验证失败",
                "code": "VALIDATION_ERROR",
                "details": [
                    {"field": "message", "message": "字段不能为空"},
                    {"field": "rating", "message": "评分必须在1-5之间"}
                ]
            },
            "timestamp": "2024-01-01T00:00:00"
        }
        ```
    """
    error: APIErrorDetail = Field(description="错误详情")  # type: ignore[assignment]
    details: List[Dict[str, str]] = Field(default_factory=list, description="字段级错误详情")


# ============================================================================
# WebSocket消息模型
# ============================================================================

class WebSocketMessage(BaseModel):
    """
    WebSocket客户端消息

    客户端通过WebSocket发送的消息格式。

    示例（聊天）:
        ```json
        {"action": "chat", "message": "你好", "session_id": "s1", "user_id": "u1"}
        ```

    示例（ping）:
        ```json
        {"action": "ping"}
        ```
    """
    action: str = Field(description="操作类型: chat/ping/stop")
    message: str = Field(default="", description="消息内容（chat操作）")
    session_id: str = Field(default="default", description="会话ID")
    user_id: str = Field(default="anonymous", description="用户ID")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """验证操作类型"""
        allowed = {"chat", "ping", "stop"}
        if v not in allowed:
            raise ValueError(f"无效的操作类型: {v}，允许的值: {allowed}")
        return v
