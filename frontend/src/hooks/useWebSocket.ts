import { useState, useCallback, useRef, useEffect } from 'react';
import type { Message, StreamChunk, Question } from '../types';

interface UseWebSocketReturn {
  messages: Message[];
  sendMessage: (content: string) => void;
  isConnected: boolean;
  isThinking: boolean;
  clearMessages: () => void;
  error: string | null;
}

// 通过vite代理连接后端WebSocket（避免跨端口安全限制）
const WS_URL = 'ws://localhost:5173/api/chat/ws';
const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 30000;
const HEARTBEAT_INTERVAL = 30000;
const MAX_RECONNECT_COUNT = 5;

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentAssistantMsgRef = useRef<Message | null>(null);
  const sessionIdRef = useRef(sessionId);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback((ws: WebSocket) => {
    clearHeartbeat();
    heartbeatTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL);
  }, [clearHeartbeat]);

  const handleStreamChunk = useCallback((chunk: StreamChunk) => {
    switch (chunk.type) {
      case 'thinking': {
        setIsThinking(true);
        currentAssistantMsgRef.current = {
          id: generateId(),
          role: 'assistant',
          content: '',
          thinking: chunk.content,
          timestamp: new Date(),
        };
        break;
      }

      case 'content': {
        setIsThinking(false);
        if (currentAssistantMsgRef.current) {
          currentAssistantMsgRef.current = {
            ...currentAssistantMsgRef.current,
            content: currentAssistantMsgRef.current.content + chunk.content,
          };
          setMessages(prev => {
            const filtered = prev.filter(
              m => m.id !== currentAssistantMsgRef.current?.id
            );
            return [...filtered, currentAssistantMsgRef.current!];
          });
        }
        break;
      }

      case 'questions': {
        if (currentAssistantMsgRef.current && chunk.questions) {
          currentAssistantMsgRef.current = {
            ...currentAssistantMsgRef.current,
            questions: chunk.questions,
          };
          setMessages(prev => {
            const filtered = prev.filter(
              m => m.id !== currentAssistantMsgRef.current?.id
            );
            return [...filtered, currentAssistantMsgRef.current!];
          });
        }
        break;
      }

      case 'references': {
        if (currentAssistantMsgRef.current && chunk.references) {
          currentAssistantMsgRef.current = {
            ...currentAssistantMsgRef.current,
            references: chunk.references,
          };
          setMessages(prev => {
            const filtered = prev.filter(
              m => m.id !== currentAssistantMsgRef.current?.id
            );
            return [...filtered, currentAssistantMsgRef.current!];
          });
        }
        break;
      }

      case 'done': {
        setIsThinking(false);
        currentAssistantMsgRef.current = null;
        break;
      }

      case 'error': {
        setIsThinking(false);
        const errorMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: `⚠️ 连接异常：${chunk.content}`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMsg]);
        currentAssistantMsgRef.current = null;
        break;
      }
    }
  }, []);

  const connect = useCallback(() => {
    try {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      console.log('[WebSocket] Connecting to', WS_URL);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        setError(null);
        reconnectAttemptRef.current = 0;
        startHeartbeat(ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return;
          handleStreamChunk(data as StreamChunk);
        } catch (err) {
          console.error('[WebSocket] Parse error:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        clearHeartbeat();

        if (reconnectAttemptRef.current < MAX_RECONNECT_COUNT) {
          const delay = Math.min(
            RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptRef.current),
            RECONNECT_MAX_DELAY
          );
          reconnectAttemptRef.current += 1;
          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current})`);
          reconnectTimerRef.current = setTimeout(connect, delay);
        } else {
          setError('连接已断开，请刷新页面重试');
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setIsConnected(false);
      };
    } catch (err) {
      console.error('[WebSocket] Connection failed:', err);
      setIsConnected(false);
      setError('无法连接到服务器');
    }
  }, [clearHeartbeat, startHeartbeat, handleStreamChunk]);

  useEffect(() => {
    connect();

    return () => {
      clearHeartbeat();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, clearHeartbeat]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket未连接');
      const errorMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: '⚠️ 连接未建立，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
      return;
    }

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    const payload = {
      message: content,
      session_id: sessionIdRef.current,
      user_id: 'user-' + sessionIdRef.current,
    };

    wsRef.current.send(JSON.stringify(payload));
    setIsThinking(true);
    setError(null);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    currentAssistantMsgRef.current = null;
    setError(null);
  }, []);

  return {
    messages,
    sendMessage,
    isConnected,
    isThinking,
    clearMessages,
    error,
  };
}
