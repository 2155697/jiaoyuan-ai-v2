import { useState, useCallback, useEffect } from 'react';
import { Header } from './components/Header';
import { ChatContainer } from './components/ChatContainer';
import { InputArea } from './components/InputArea';
import { Sidebar } from './components/Sidebar';
import { useWebSocket } from './hooks/useWebSocket';
import type { Session, CognitiveState } from './types';

/**
 * 教员AI顾问 - 主应用组件
 *
 * 布局结构：
 * ┌─────────────────────────────────────┐
 * │  Sidebar  │  Header                 │
 * │           ├─────────────────────────┤
 * │  会话列表  │  ChatContainer          │
 * │  认知状态  │  聊天消息区域            │
 * │           │                         │
 * │           ├─────────────────────────┤
 * │           │  InputArea              │
 * │           │  输入框+快捷提示         │
 * └─────────────────────────────────────┘
 */

// 生成唯一ID
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

// 创建新会话
function createSession(): Session {
  const now = new Date();
  return {
    id: generateId(),
    title: '',
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

// 模拟认知状态（后续从后端获取）
const mockCognitiveState: CognitiveState = {
  goal: '识别核心矛盾',
  plan: '制定分析框架',
  link: '定位关键环节',
  need: '明确真实需求',
  factor: '评估内外因素',
  evaluate: '反馈调整方案',
};

function App() {
  // 会话管理
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // WebSocket 连接
  const { messages, sendMessage, isConnected, isThinking, clearMessages } =
    useWebSocket(currentSessionId);

  // 初始化默认会话
  useEffect(() => {
    if (sessions.length === 0) {
      const defaultSession = createSession();
      setSessions([defaultSession]);
      setCurrentSessionId(defaultSession.id);
    }
  }, [sessions.length]);

  // 同步消息到当前会话
  useEffect(() => {
    if (!currentSessionId || messages.length === 0) return;

    setSessions((prev) =>
      prev.map((session) => {
        if (session.id === currentSessionId) {
          // 更新会话标题（从第一条用户消息获取）
          let title = session.title;
          if (!title) {
            const firstUserMsg = messages.find((m) => m.role === 'user');
            if (firstUserMsg) {
              title =
                firstUserMsg.content.slice(0, 20) +
                (firstUserMsg.content.length > 20 ? '...' : '');
            }
          }

          return {
            ...session,
            messages: [...messages],
            title,
            updatedAt: new Date(),
          };
        }
        return session;
      })
    );
  }, [messages, currentSessionId]);

  // 创建新会话
  const handleNewSession = useCallback(() => {
    const newSession = createSession();
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    clearMessages();
    setSidebarOpen(false);
  }, [clearMessages]);

  // 切换会话
  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      if (sessionId === currentSessionId) return;

      setCurrentSessionId(sessionId);
      clearMessages();

      // 加载会话历史消息（如果有）
      const session = sessions.find((s) => s.id === sessionId);
      if (session && session.messages.length > 0) {
        // 这里需要一种方式将历史消息加载到 WebSocket hook 中
        // 简化处理：通过页面刷新或状态提升来实现
      }

      setSidebarOpen(false);
    },
    [currentSessionId, sessions, clearMessages]
  );

  // 删除会话
  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== sessionId);

        // 如果删除的是当前会话，切换到第一个会话
        if (sessionId === currentSessionId) {
          if (filtered.length > 0) {
            setCurrentSessionId(filtered[0].id);
            clearMessages();
          } else {
            // 如果没有会话了，创建一个新会话
            const newSession = createSession();
            filtered.push(newSession);
            setCurrentSessionId(newSession.id);
            clearMessages();
          }
        }

        return filtered;
      });
    },
    [currentSessionId, clearMessages]
  );

  // 发送消息
  const handleSendMessage = useCallback(
    (content: string) => {
      sendMessage(content);
    },
    [sendMessage]
  );

  // 切换侧边栏（移动端）
  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  // 获取当前会话
  const currentSession = sessions.find((s) => s.id === currentSessionId);

  return (
    <div className="h-screen flex flex-col bg-background dark:bg-background-dark overflow-hidden">
      {/* 顶部标题栏 */}
      <Header
        isConnected={isConnected}
        onMenuClick={toggleSidebar}
        sidebarOpen={sidebarOpen}
      />

      {/* 主体区域 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 侧边栏 */}
        <Sidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSessionSelect={handleSessionSelect}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          cognitiveState={mockCognitiveState}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* 聊天区域 */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* 聊天消息容器 */}
          <ChatContainer
            messages={currentSession?.messages || messages}
            isThinking={isThinking}
          />

          {/* 底部输入区域 */}
          <InputArea
            onSendMessage={handleSendMessage}
            isThinking={isThinking}
            disabled={!isConnected}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
