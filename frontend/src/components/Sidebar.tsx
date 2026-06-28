import { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Trash2,
  ChevronRight,
  Target,
  FileText,
  MapPin,
  Search,
  Settings,
  BarChart3,
  RefreshCw,
  X,
} from 'lucide-react';
import type { Session, CognitiveState } from '../types';

interface SidebarProps {
  sessions: Session[];
  currentSessionId: string;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  cognitiveState?: CognitiveState;
  isOpen: boolean;
  onClose: () => void;
}

// 认知状态节点配置
const COGNITIVE_NODES: {
  key: keyof CognitiveState;
  label: string;
  icon: React.ReactNode;
  color: string;
}[] = [
  { key: 'goal', label: '目标', icon: <Target className="w-3.5 h-3.5" />, color: '#C0392B' },
  { key: 'plan', label: '方案', icon: <FileText className="w-3.5 h-3.5" />, color: '#E67E22' },
  { key: 'link', label: '环节', icon: <MapPin className="w-3.5 h-3.5" />, color: '#F1C40F' },
  { key: 'need', label: '需求', icon: <Search className="w-3.5 h-3.5" />, color: '#27AE60' },
  { key: 'factor', label: '因素', icon: <Settings className="w-3.5 h-3.5" />, color: '#3498DB' },
  { key: 'evaluate', label: '评估', icon: <BarChart3 className="w-3.5 h-3.5" />, color: '#9B59B6' },
];

// 认知状态可视化组件
function CognitiveCycle({ state }: { state: CognitiveState }) {
  const [activeIndex, setActiveIndex] = useState(0);

  // 自动循环展示
  useState(() => {
    const timer = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % COGNITIVE_NODES.length);
    }, 2000);
    return () => clearInterval(timer);
  });

  return (
    <div className="px-3 py-3">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
        <RefreshCw className="w-3.5 h-3.5" />
        认知状态循环
      </h3>

      {/* 循环可视化 */}
      <div className="flex flex-col gap-2">
        {COGNITIVE_NODES.map((node, index) => {
          const value = state[node.key];
          const isActive = index === activeIndex;

          return (
            <div
              key={node.key}
              className={`flex items-center gap-2.5 p-2 rounded-lg transition-all duration-300 ${
                isActive
                  ? 'bg-primary/10 border border-primary/20'
                  : 'bg-transparent border border-transparent'
              }`}
            >
              {/* 节点图标 */}
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                style={{
                  backgroundColor: isActive ? `${node.color}20` : '#f0ebe5',
                  color: isActive ? node.color : '#9B8B7B',
                }}
              >
                {node.icon}
              </div>

              {/* 标签 + 值 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span
                    className="text-xs font-medium"
                    style={{ color: isActive ? node.color : '#6B5B4F' }}
                  >
                    {node.label}
                  </span>
                  {isActive && (
                    <ChevronRight className="w-3 h-3" style={{ color: node.color }} />
                  )}
                </div>
                {value && (
                  <p className="text-[11px] text-text-muted truncate mt-0.5">{value}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 循环箭头指示 */}
      <div className="flex justify-center mt-2">
        <div className="flex items-center gap-1 text-[10px] text-text-muted">
          <RefreshCw className="w-3 h-3 animate-spin-slow" />
          <span>六步认知循环</span>
        </div>
      </div>
    </div>
  );
}

export function Sidebar({
  sessions,
  currentSessionId,
  onSessionSelect,
  onNewSession,
  onDeleteSession,
  cognitiveState,
  isOpen,
  onClose,
}: SidebarProps) {
  const [hoveredSession, setHoveredSession] = useState<string | null>(null);

  // 格式化会话时间
  const formatTime = (date: Date) => {
    const d = new Date(date);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return '昨天';
    } else if (days < 7) {
      return `${days}天前`;
    } else {
      return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  // 获取会话简短标题
  const getSessionTitle = (session: Session) => {
    if (session.title) return session.title;
    const firstUserMsg = session.messages.find((m) => m.role === 'user');
    if (firstUserMsg) {
      return firstUserMsg.content.slice(0, 20) + (firstUserMsg.content.length > 20 ? '...' : '');
    }
    return '新对话';
  };

  const sidebarContent = (
    <>
      {/* 新建会话按钮 */}
      <div className="p-3">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-white rounded-lg hover:bg-primary-dark transition-all shadow-soft hover:shadow-medium active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm font-medium">新对话</span>
        </button>
      </div>

      {/* 分割线 */}
      <div className="mx-3 h-px bg-border" />

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto py-2">
        <div className="px-3 mb-2">
          <span className="text-[11px] text-text-muted uppercase tracking-wider">
            历史会话 ({sessions.length})
          </span>
        </div>

        {sessions.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <MessageSquare className="w-8 h-8 text-border mx-auto mb-2" />
            <p className="text-xs text-text-muted">暂无会话记录</p>
            <p className="text-[11px] text-text-muted mt-1">点击上方按钮开始新对话</p>
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className={`session-item mx-2 px-3 py-2.5 cursor-pointer flex items-center gap-2.5 group ${
                session.id === currentSessionId ? 'active' : ''
              }`}
              onClick={() => {
                onSessionSelect(session.id);
                onClose();
              }}
              onMouseEnter={() => setHoveredSession(session.id)}
              onMouseLeave={() => setHoveredSession(null)}
            >
              {/* 会话图标 */}
              <div className="shrink-0 w-8 h-8 rounded-lg bg-secondary/20 flex items-center justify-center">
                <MessageSquare className="w-4 h-4 text-secondary-dark" />
              </div>

              {/* 会话信息 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text truncate">{getSessionTitle(session)}</p>
                <p className="text-[11px] text-text-muted flex items-center gap-1">
                  <span>{session.messages.length} 条消息</span>
                  <span>·</span>
                  <span>{formatTime(session.updatedAt)}</span>
                </p>
              </div>

              {/* 删除按钮 */}
              {(hoveredSession === session.id || session.id === currentSessionId) && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="shrink-0 p-1 rounded hover:bg-accent/10 text-text-muted hover:text-accent transition-colors opacity-0 group-hover:opacity-100"
                  title="删除会话"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* 分割线 */}
      {cognitiveState && <div className="mx-3 h-px bg-border" />}

      {/* 认知状态 */}
      {cognitiveState && <CognitiveCycle state={cognitiveState} />}

      {/* 底部信息 */}
      <div className="p-3 border-t border-border">
        <p className="text-[10px] text-text-muted text-center">
          教员AI顾问 v1.0 · 用教员的思维方式思考问题
        </p>
      </div>
    </>
  );

  return (
    <>
      {/* 移动端遮罩 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-30 md:hidden"
          onClick={onClose}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-72 bg-surface border-r border-border flex flex-col transition-transform duration-300 ease-spring md:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* 移动端关闭按钮 */}
        <div className="md:hidden flex justify-end p-2">
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-primary/5 transition-colors"
          >
            <X className="w-5 h-5 text-text" />
          </button>
        </div>

        {sidebarContent}
      </aside>
    </>
  );
}
