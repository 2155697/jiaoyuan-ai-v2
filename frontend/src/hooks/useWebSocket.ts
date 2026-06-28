import { useState, useCallback, useRef, useEffect } from 'react';
import type { Message } from '../types';

interface UseWebSocketReturn {
  messages: Message[];
  sendMessage: (content: string) => void;
  isConnected: boolean;
  isThinking: boolean;
  clearMessages: () => void;
  error: string | null;
}

// WebSocket服务器地址
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat';

// 生成唯一ID
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * WebSocket连接管理Hook
 *
 * 管理WebSocket连接和消息通信：
 * - 自动连接/重连
 * - 消息收发
 * - 连接状态管理
 * - 心跳保活
 *
 * 用法:
 * ```tsx
 * const { messages, sendMessage, isConnected, isThinking, clearMessages } = useWebSocket(sessionId);
 * ```
 */
export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectCountRef = useRef(0);
  const maxReconnectCount = 5;

  // 连接WebSocket
  const connect = useCallback(() => {
    // 如果已有连接，先关闭
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      setError(null);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] 连接已建立');
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;

        // 启动心跳
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch (err) {
          console.error('[WebSocket] 消息解析失败:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WebSocket] 连接已关闭');
        setIsConnected(false);
        stopHeartbeat();

        // 尝试重连
        if (reconnectCountRef.current < maxReconnectCount) {
          const delay = Math.min(1000 * Math.pow(2, reconnectCountRef.current), 30000);
          reconnectCountRef.current++;

          reconnectTimerRef.current = setTimeout(() => {
            console.log(`[WebSocket] 第${reconnectCountRef.current}次重连...`);
            connect();
          }, delay);
        } else {
          setError('连接已断开，请刷新页面重试');
        }
      };

      ws.onerror = (err) => {
        console.error('[WebSocket] 连接错误:', err);
        setIsConnected(false);
      };
    } catch (err) {
      console.error('[WebSocket] 创建连接失败:', err);
      setError('无法连接到服务器');
    }
  }, []);

  // 停止心跳
  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // 处理服务器消息
  const handleServerMessage = useCallback((data: any) => {
    switch (data.type) {
      case 'status':
        // 状态更新（如："正在分析矛盾..."）
        if (data.content) {
          setIsThinking(true);
        }
        break;

      case 'thinking':
        // 思考过程（不显示给用户，可用于调试）
        console.log('[思考]', data.content);
        break;

      case 'content':
        // 增量内容
        setIsThinking(false);
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
            // 追加到上一条AI消息
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMsg,
              content: lastMsg.content + (data.content || ''),
            };
            return updated;
          }
          // 创建新消息
          return [
            ...prev,
            {
              id: generateId(),
              role: 'assistant',
              content: data.content || '',
              timestamp: new Date(),
              isStreaming: true,
            },
          ];
        });
        break;

      case 'complete':
        // 消息完成
        setIsThinking(false);
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMsg,
              content: data.content || lastMsg.content,
              isStreaming: false,
              thinking: data.thinking,
              questions: data.questions,
              references: data.references,
              contradictions: data.contradictions,
              stage: data.stage,
              fiveLayer: data.fiveLayer,
            };
            return updated;
          }
          return prev;
        });
        break;

      case 'error':
        // 错误消息
        setIsThinking(false);
        setError(data.content || '未知错误');
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: `抱歉，处理过程中出现错误：${data.content || '未知错误'}`,
            timestamp: new Date(),
          },
        ]);
        break;

      case 'pong':
        // 心跳响应
        break;

      default:
        console.log('[WebSocket] 未知消息类型:', data.type, data);
    }
  }, []);

  // 发送消息
  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError('WebSocket未连接');
        return;
      }

      // 添加用户消息到列表
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsThinking(true);
      setError(null);

      // 发送给服务器
      wsRef.current.send(
        JSON.stringify({
          type: 'chat',
          content,
          session_id: sessionId,
        })
      );
    },
    [sessionId]
  );

  // 清空消息
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  // 初始连接
  useEffect(() => {
    connect();

    return () => {
      // 清理
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      stopHeartbeat();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, stopHeartbeat]);

  return {
    messages,
    sendMessage,
    isConnected,
    isThinking,
    clearMessages,
    error,
  };
}
