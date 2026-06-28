"""
教员AI顾问 API - WebSocket连接管理器

管理WebSocket连接，支持多会话并发：
- 连接管理：接受、断开、清理
- 会话隔离：每个会话ID对应一组连接
- 广播功能：向指定会话的所有连接发送消息
- 并发安全：使用异步锁保护共享状态
- 自动清理：断开时清理资源

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("jiaoyuan.api.websocket")


# ============================================================================
# WebSocket连接元数据
# ============================================================================

class ConnectionInfo:
    """WebSocket连接信息"""

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        connected_at: float = 0.0,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.user_id = user_id
        self.connected_at = connected_at or time.time()
        self.last_activity = self.connected_at
        self.message_count = 0
        self.is_active = True

    def touch(self) -> None:
        """更新最后活动时间"""
        self.last_activity = time.time()
        self.message_count += 1

    @property
    def connection_duration(self) -> float:
        """连接持续时间（秒）"""
        return time.time() - self.connected_at

    @property
    def idle_time(self) -> float:
        """空闲时间（秒）"""
        return time.time() - self.last_activity

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "connected_at": self.connected_at,
            "last_activity": self.last_activity,
            "message_count": self.message_count,
            "connection_duration": round(self.connection_duration, 2),
            "idle_time": round(self.idle_time, 2),
            "is_active": self.is_active,
        }


# ============================================================================
# WebSocket管理器
# ============================================================================

class WebSocketManager:
    """
    WebSocket连接管理器

    管理所有WebSocket连接，支持：
    - 多会话并发（同一session_id可以有多个连接）
    - 会话隔离（广播只发送到同session的连接）
    - 连接统计和监控
    - 优雅断开和清理

    用法:
        ```python
        manager = WebSocketManager()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await manager.connect(websocket, session_id="s1", user_id="u1")
            try:
                while True:
                    data = await websocket.receive_json()
                    await manager.broadcast(session_id="s1", message={"type": "echo", ...})
            except WebSocketDisconnect:
                await manager.disconnect(websocket, session_id="s1")
        ```
    """

    def __init__(self):
        # session_id -> Set[ConnectionInfo]
        self._connections: Dict[str, Set[ConnectionInfo]] = {}
        # websocket -> ConnectionInfo（反向索引）
        self._conn_map: Dict[WebSocket, ConnectionInfo] = {}
        # 保护共享状态的锁
        self._lock = asyncio.Lock()
        # 关闭标志
        self._closed = False

        logger.info("WebSocketManager initialized")

    # ========================================================================
    # 连接管理
    # ========================================================================

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str = "anonymous",
    ) -> ConnectionInfo:
        """
        接受新的WebSocket连接

        Args:
            websocket: FastAPI WebSocket对象
            session_id: 会话ID（用于会话隔离）
            user_id: 用户ID

        Returns:
            ConnectionInfo连接信息
        """
        await websocket.accept()

        conn_info = ConnectionInfo(
            websocket=websocket,
            session_id=session_id,
            user_id=user_id,
        )

        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(conn_info)
            self._conn_map[websocket] = conn_info

        logger.info(
            "WebSocket connected: session=%s, user=%s, total_conns=%d",
            session_id,
            user_id,
            len(self._conn_map),
        )

        return conn_info

    async def disconnect(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
    ) -> None:
        """
        断开WebSocket连接

        Args:
            websocket: 要断开的WebSocket对象
            session_id: 可选的会话ID（加速查找）
        """
        conn_info: Optional[ConnectionInfo] = None

        async with self._lock:
            conn_info = self._conn_map.pop(websocket, None)

            if conn_info:
                target_session = session_id or conn_info.session_id
                if target_session in self._connections:
                    self._connections[target_session].discard(conn_info)
                    # 如果该会话没有连接了，清理空集合
                    if not self._connections[target_session]:
                        del self._connections[target_session]

        if conn_info:
            logger.info(
                "WebSocket disconnected: session=%s, user=%s, duration=%.1fs, messages=%d, remaining=%d",
                conn_info.session_id,
                conn_info.user_id,
                conn_info.connection_duration,
                conn_info.message_count,
                len(self._conn_map),
            )
        else:
            logger.debug("WebSocket disconnected: unknown connection")

    # ========================================================================
    # 消息发送
    # ========================================================================

    async def send(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
    ) -> bool:
        """
        向单个连接发送消息

        Args:
            websocket: 目标WebSocket
            message: 要发送的字典消息

        Returns:
            是否发送成功
        """
        try:
            await websocket.send_json(message)

            # 更新连接活动状态
            conn_info = self._conn_map.get(websocket)
            if conn_info:
                conn_info.touch()

            return True

        except Exception as e:
            logger.warning("Failed to send message: %s", e)
            return False

    async def broadcast(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> int:
        """
        向指定会话的所有连接广播消息

        Args:
            session_id: 目标会话ID
            message: 要发送的字典消息

        Returns:
            成功发送的连接数
        """
        connections = self._get_session_connections(session_id)
        if not connections:
            return 0

        sent_count = 0
        dead_connections: List[ConnectionInfo] = []

        for conn_info in connections:
            try:
                await conn_info.websocket.send_json(message)
                conn_info.touch()
                sent_count += 1
            except Exception as e:
                logger.debug("Broadcast failed to connection: %s", e)
                conn_info.is_active = False
                dead_connections.append(conn_info)

        # 清理失效连接
        if dead_connections:
            await self._cleanup_dead_connections(session_id, dead_connections)

        return sent_count

    async def send_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
    ) -> int:
        """
        向指定用户的所有连接发送消息（跨会话）

        Args:
            user_id: 目标用户ID
            message: 要发送的字典消息

        Returns:
            成功发送的连接数
        """
        sent_count = 0
        dead_connections: List[ConnectionInfo] = []

        for conn_info in self._conn_map.values():
            if conn_info.user_id != user_id:
                continue

            try:
                await conn_info.websocket.send_json(message)
                conn_info.touch()
                sent_count += 1
            except Exception as e:
                logger.debug("Send to user failed: %s", e)
                conn_info.is_active = False
                dead_connections.append(conn_info)

        # 清理失效连接
        if dead_connections:
            for conn_info in dead_connections:
                await self.disconnect(conn_info.websocket)

        return sent_count

    async def send_error(
        self,
        websocket: WebSocket,
        error_message: str,
        error_code: str = "INTERNAL_ERROR",
    ) -> bool:
        """
        向连接发送错误消息

        Args:
            websocket: 目标WebSocket
            error_message: 错误描述
            error_code: 错误代码

        Returns:
            是否发送成功
        """
        return await self.send(websocket, {
            "type": "error",
            "content": error_message,
            "code": error_code,
            "timestamp": time.time(),
        })

    # ========================================================================
    # 流式对话处理
    # ========================================================================

    async def handle_chat_stream(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        message: str,
        engine: Any,  # JiaoyuanEngine
    ) -> None:
        """
        处理流式对话请求

        从引擎获取流式输出，实时转发给客户端。

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
            user_id: 用户ID
            message: 用户消息
            engine: JiaoyuanEngine实例
        """
        logger.info(
            "Stream chat: session=%s, user=%s, message='%s...'",
            session_id,
            user_id,
            message[:50],
        )

        try:
            async for chunk in engine.chat_stream(message, session_id, user_id):
                success = await self.send(websocket, chunk)
                if not success:
                    logger.warning("Stream send failed, aborting")
                    break

        except Exception as e:
            logger.exception("Stream chat error: %s", e)
            await self.send_error(
                websocket,
                f"流式处理出错: {str(e)}",
                error_code="STREAM_ERROR",
            )

    # ========================================================================
    # 查询和统计
    # ========================================================================

    def get_session_connections(self, session_id: str) -> List[ConnectionInfo]:
        """
        获取指定会话的所有连接信息

        Args:
            session_id: 会话ID

        Returns:
            ConnectionInfo列表
        """
        return self._get_session_connections(session_id)

    def _get_session_connections(self, session_id: str) -> List[ConnectionInfo]:
        """内部方法：获取会话连接（不加锁）"""
        conns = self._connections.get(session_id, set())
        return [c for c in conns if c.is_active]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取WebSocket统计信息

        Returns:
            统计信息字典
        """
        session_count = len(self._connections)
        total_connections = len(self._conn_map)

        # 按会话统计
        session_stats = {}
        for sid, conns in self._connections.items():
            active = sum(1 for c in conns if c.is_active)
            session_stats[sid] = {
                "total": len(conns),
                "active": active,
                "users": list(set(c.user_id for c in conns)),
            }

        return {
            "total_connections": total_connections,
            "active_sessions": session_count,
            "session_stats": session_stats,
        }

    async def get_connection_details(self) -> List[Dict[str, Any]]:
        """
        获取所有连接详情

        Returns:
            连接信息字典列表
        """
        return [conn.to_dict() for conn in self._conn_map.values()]

    # ========================================================================
    # 清理和维护
    # ========================================================================

    async def cleanup_idle_connections(
        self,
        max_idle_seconds: float = 3600.0,
    ) -> int:
        """
        清理空闲连接

        Args:
            max_idle_seconds: 最大空闲时间（秒）

        Returns:
            清理的连接数
        """
        now = time.time()
        to_close: List[ConnectionInfo] = []

        for conn_info in list(self._conn_map.values()):
            if conn_info.idle_time > max_idle_seconds:
                to_close.append(conn_info)

        for conn_info in to_close:
            try:
                await conn_info.websocket.close(code=1000, reason="Idle timeout")
            except Exception:
                pass
            await self.disconnect(conn_info.websocket)

        if to_close:
            logger.info("Cleaned up %d idle connections", len(to_close))

        return len(to_close)

    async def _cleanup_dead_connections(
        self,
        session_id: str,
        dead_connections: List[ConnectionInfo],
    ) -> None:
        """清理失效连接"""
        async with self._lock:
            if session_id in self._connections:
                for conn in dead_connections:
                    self._connections[session_id].discard(conn)
                    self._conn_map.pop(conn.websocket, None)

                if not self._connections[session_id]:
                    del self._connections[session_id]

    async def close_all(self) -> None:
        """关闭所有连接（优雅关闭）"""
        self._closed = True

        # 复制列表避免遍历时修改
        all_connections = list(self._conn_map.values())

        for conn_info in all_connections:
            try:
                await conn_info.websocket.close(
                    code=1001,
                    reason="Server shutting down",
                )
            except Exception:
                pass

        # 清空状态
        self._connections.clear()
        self._conn_map.clear()

        logger.info("All WebSocket connections closed (%d)", len(all_connections))

    # ========================================================================
    # 生命周期管理
    # ========================================================================

    @property
    def is_closed(self) -> bool:
        """管理器是否已关闭"""
        return self._closed

    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._conn_map)

    @property
    def session_count(self) -> int:
        """当前会话数"""
        return len(self._connections)


# ============================================================================
# 全局实例
# ============================================================================

# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()
