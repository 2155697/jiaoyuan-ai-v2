"""教员AI顾问 API - WebSocket连接管理器

管理WebSocket连接，支持多会话并发：
- 连接管理：接受、断开、清理
- 会话隔离：每个会话ID对应一组连接
- 广播功能：向指定会话的所有连接发送消息
- 并发安全：使用异步锁保护共享状态
- 自动清理：断开时清理资源

作者: AI系统架构师
版本: 3.0.1
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("jiaoyuan.api.websocket")


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
        self.last_activity = time.time()
        self.message_count += 1

    @property
    def connection_duration(self) -> float:
        return time.time() - self.connected_at

    @property
    def idle_time(self) -> float:
        return time.time() - self.last_activity

    def to_dict(self) -> Dict[str, Any]:
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


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self._connections: Dict[str, Set[ConnectionInfo]] = {}
        self._conn_map: Dict[WebSocket, ConnectionInfo] = {}
        self._lock = asyncio.Lock()
        self._closed = False

        logger.info("WebSocketManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str = "anonymous",
    ) -> ConnectionInfo:
        """
        注册已接受的 WebSocket 连接。
        注意：调用方需要先 await websocket.accept() 再调用本方法。
        """
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
        conn_info: Optional[ConnectionInfo] = None

        async with self._lock:
            conn_info = self._conn_map.pop(websocket, None)

            if conn_info:
                target_session = session_id or conn_info.session_id
                if target_session in self._connections:
                    self._connections[target_session].discard(conn_info)
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

    async def send(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
    ) -> bool:
        try:
            await websocket.send_json(message)
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

        if dead_connections:
            await self._cleanup_dead_connections(session_id, dead_connections)

        return sent_count

    async def send_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
    ) -> int:
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
        return await self.send(websocket, {
            "type": "error",
            "content": error_message,
            "code": error_code,
            "timestamp": time.time(),
        })

    async def handle_chat_stream(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        message: str,
        engine: Any,
    ) -> None:
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

    def _get_session_connections(self, session_id: str) -> List[ConnectionInfo]:
        conns = self._connections.get(session_id, set())
        return [c for c in conns if c.is_active]

    def get_stats(self) -> Dict[str, Any]:
        session_count = len(self._connections)
        total_connections = len(self._conn_map)

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
        return [conn.to_dict() for conn in self._conn_map.values()]

    async def cleanup_idle_connections(
        self,
        max_idle_seconds: float = 3600.0,
    ) -> int:
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
        async with self._lock:
            if session_id in self._connections:
                for conn in dead_connections:
                    self._connections[session_id].discard(conn)
                    self._conn_map.pop(conn.websocket, None)

                if not self._connections[session_id]:
                    del self._connections[session_id]

    async def close_all(self) -> None:
        self._closed = True

        all_connections = list(self._conn_map.values())

        for conn_info in all_connections:
            try:
                await conn_info.websocket.close(
                    code=1001,
                    reason="Server shutting down",
                )
            except Exception:
                pass

        self._connections.clear()
        self._conn_map.clear()

        logger.info("All WebSocket connections closed (%d)", len(all_connections))

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def connection_count(self) -> int:
        return len(self._conn_map)

    @property
    def session_count(self) -> int:
        return len(self._connections)


websocket_manager = WebSocketManager()
