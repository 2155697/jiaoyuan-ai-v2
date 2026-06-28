import { useState, useCallback, useEffect } from 'react';
import { Header } from './components/Header';
import { ChatContainer } from './components/ChatContainer';
import { InputArea } from './components/InputArea';
import { Sidebar } from './components/Sidebar';
import { useWebSocket } from './hooks/useWebSocket';
import type { Session, CognitiveState } from './types';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

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

const mockCognitiveState: CognitiveState = {
  goal: '识别核心矛盾',
  plan: '制定分析框架',
  link: '定位关键环节',
  need: '明确真实需求',
  factor: '评估内外因素',
  evaluate: '反馈调整方案',
};

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { messages, sendMessage, isConnected, isThinking, clearMessages, progress, thinkingChunks } =
    useWebSocket(currentSessionId);

  useEffect(() => {
    if (sessions.length === 0) {
      const defaultSession = createSession();
      setSessions([defaultSession]);
      setCurrentSessionId(defaultSession.id);
    }
  }, [sessions.length]);

  useEffect(() => {
    if (!currentSessionId || messages.length === 0) return;
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id === currentSessionId) {
          let title = session.title;
          if (!title) {
            const firstUserMsg = messages.find((m) => m.role === 'user');
            if (firstUserMsg) {
              title = firstUserMsg.content.slice(0, 20) + (firstUserMsg.content.length > 20 ? '...' : '');
            }
          }
          return { ...session, messages: [...messages], title, updatedAt: new Date() };
        }
        return session;
      })
    );
  }, [messages, currentSessionId]);

  const handleNewSession = useCallback(() => {
    const newSession = createSession();
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    clearMessages();
    setSidebarOpen(false);
  }, [clearMessages]);

  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      if (sessionId === currentSessionId) return;
      setCurrentSessionId(sessionId);
      clearMessages();
      setSidebarOpen(false);
    },
    [currentSessionId, clearMessages]
  );

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== sessionId);
        if (sessionId === currentSessionId) {
          if (filtered.length > 0) {
            setCurrentSessionId(filtered[0].id);
            clearMessages();
          } else {
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

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const currentSession = sessions.find((s) => s.id === currentSessionId);

  return (
    <div className="h-screen flex flex-col bg-background dark:bg-background-dark overflow-hidden">
      <Header isConnected={isConnected} onMenuClick={toggleSidebar} sidebarOpen={sidebarOpen} />
      <div className="flex-1 flex overflow-hidden">
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
        <div className="flex-1 flex flex-col min-w-0">
          <ChatContainer
            messages={currentSession?.messages || messages}
            isThinking={isThinking}
            progress={progress}
            thinkingChunks={thinkingChunks}
          />
          <InputArea onSendMessage={sendMessage} isThinking={isThinking} disabled={!isConnected} />
        </div>
      </div>
    </div>
  );
}

export default App;
