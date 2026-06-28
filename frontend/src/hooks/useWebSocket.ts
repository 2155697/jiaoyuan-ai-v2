import { useState, useRef, useCallback, useEffect } from 'react';
import type { Message, StreamChunk, Question, ProgressState } from '../types';

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
  const currentAssistantMsgRef = useRef<Message | null>(null);
  const sessionIdRef = useRef(sessionId);

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

  // Handle incoming stream chunk
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
          // Update messages list with current streaming message
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

      case 'progress': {
        setProgress({
          step: chunk.step || 0,
          total: chunk.total || 5,
          label: chunk.label || '',
          detail: chunk.detail || '',
        });
        break;
      }

      case 'thinking_chunk': {
        setThinkingChunks(prev => [...prev, chunk.content]);
        break;
      }

      case 'done': {
        setIsThinking(false);
        setProgress(null);
        setThinkingChunks([]);
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

  // Connect WebSocket
  const connect = useCallback(() => {
    try {
      // Clear any existing reconnect timer
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

          // Handle pong
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

        // Attempt reconnection with exponential backoff
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
      // Add error message
      const errorMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: '⚠️ 连接未建立，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
      return;
    }

    // 清空之前的状态
    setThinkingChunks([]);
    setProgress(null);
    setError(null);

    // Add user message
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    // Send to server
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
    currentAssistantMsgRef.current = null;
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
