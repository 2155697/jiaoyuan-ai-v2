import { useState, useRef, useCallback, useEffect } from 'react';
import type { Message, StreamChunk, ProgressState } from '../types';

interface UseWebSocketReturn {
  messages: Message[];
  sendMessage: (content: string) => void;
  isConnected: boolean;
  isThinking: boolean;
  clearMessages: () => void;
  error: string | null;
  progress: ProgressState | null;
  thinkingChunks: string[];
}

// 通过vite代理连接后端（避免浏览器跨端口安全限制）
const WS_URL = 'ws://localhost:5173/api/chat/ws';
const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 30000;
const HEARTBEAT_INTERVAL = 30000;
const MAX_RECONNECT_ATTEMPTS = 5; // 最大重连次数限制

export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [thinkingChunks, setThinkingChunks] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef(sessionId);

  // 优化：使用 ref 缓存当前消息，减少 setState 触发
  const currentMsgRef = useRef<Message | null>(null);
  const contentBufferRef = useRef('');
  const pendingUpdateRef = useRef(false);

  // Keep sessionId ref in sync
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Generate unique message ID
  const generateId = () => {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  };

  // Clear heartbeat timer
  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // Start heartbeat
  const startHeartbeat = useCallback((ws: WebSocket) => {
    clearHeartbeat();
    heartbeatTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL);
  }, [clearHeartbeat]);

  // 优化：批量更新消息，使用 requestAnimationFrame 节流
  const flushMessageUpdate = useCallback(() => {
    pendingUpdateRef.current = false;
    if (currentMsgRef.current) {
      const msg = { ...currentMsgRef.current, content: contentBufferRef.current };
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== msg.id);
        return [...filtered, msg];
      });
    }
  }, []);

  const scheduleUpdate = useCallback(() => {
    if (!pendingUpdateRef.current) {
      pendingUpdateRef.current = true;
      requestAnimationFrame(() => {
        flushMessageUpdate();
      });
    }
  }, [flushMessageUpdate]);

  // Handle incoming stream chunk
  const handleStreamChunk = useCallback((chunk: StreamChunk) => {
    switch (chunk.type) {
      case 'thinking': {
        setIsThinking(true);
        const newMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: '',
          thinking: chunk.content,
          timestamp: new Date(),
        };
        currentMsgRef.current = newMsg;
        contentBufferRef.current = '';
        setMessages(prev => [...prev, newMsg]);
        break;
      }

      case 'content': {
        setIsThinking(false);
        contentBufferRef.current += chunk.content;
        scheduleUpdate();
        break;
      }

      case 'progress': {
        // 优化：只在步骤变化时更新，避免频繁渲染
        setProgress(prev => {
          if (prev && prev.step === chunk.step) return prev;
          return {
            step: chunk.step || 0,
            total: chunk.total || 4,
            label: chunk.label || '',
            detail: chunk.detail || '',
          };
        });
        break;
      }

      case 'thinking_chunk': {
        // 优化：限制 thinkingChunks 长度，避免无限增长
        setThinkingChunks(prev => {
          const next = [...prev, chunk.content];
          return next.length > 50 ? next.slice(-50) : next;
        });
        break;
      }

      case 'done': {
        setIsThinking(false);
        setProgress(null);
        setThinkingChunks([]);
        // 最后一次同步
        flushMessageUpdate();
        currentMsgRef.current = null;
        contentBufferRef.current = '';
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
        currentMsgRef.current = null;
        contentBufferRef.current = '';
        break;
      }
    }
  }, [flushMessageUpdate, scheduleUpdate]);

  // Connect WebSocket
  const connect = useCallback(() => {
    try {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        reconnectAttemptRef.current = 0;
        startHeartbeat(ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return;
          handleStreamChunk(data as StreamChunk);
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        clearHeartbeat();

        // 限制重连次数，避免无限重连
        if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error('[WebSocket] Max reconnect attempts reached, giving up');
          const errorMsg: Message = {
            id: generateId(),
            role: 'assistant',
            content: '⚠️ 连接已断开，请刷新页面重试。',
            timestamp: new Date(),
          };
          setMessages(prev => [...prev, errorMsg]);
          return;
        }

        const delay = Math.min(
          RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptRef.current),
          RECONNECT_MAX_DELAY
        );
        reconnectAttemptRef.current += 1;
        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current})`);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setIsConnected(false);
      };
    } catch (err) {
      console.error('[WebSocket] Connection failed:', err);
      setIsConnected(false);
    }
  }, [clearHeartbeat, startHeartbeat, handleStreamChunk]);

  // Initialize connection
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

  // Send message
  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Not connected');
      const errorMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: '⚠️ 连接未建立，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
      return;
    }

    setThinkingChunks([]);
    setProgress(null);
    setError(null);

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
  }, []);

  // Clear all messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    currentMsgRef.current = null;
    contentBufferRef.current = '';
  }, []);

  return {
    messages,
    sendMessage,
    isConnected,
    isThinking,
    clearMessages,
    error,
    progress,
    thinkingChunks,
  };
}
