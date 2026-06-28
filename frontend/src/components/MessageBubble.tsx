import { useState, useRef, useEffect } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Lightbulb,
  HelpCircle,
  AlertTriangle,
  Compass,
  Search,
  RefreshCw,
  BookOpen,
  User,
  Clock,
} from 'lucide-react';
import type { Message, Question, QuestionType } from '../types';
import { QUESTION_TYPE_CONFIG } from '../types';

interface MessageBubbleProps {
  message: Message;
  isLatest?: boolean;
}

// 根据问题类型获取图标
function QuestionTypeIcon({ type }: { type: QuestionType }) {
  const iconProps = { className: 'w-3.5 h-3.5', strokeWidth: 2 };
  switch (type) {
    case 'clarify': return <HelpCircle {...iconProps} />;
    case 'challenge': return <AlertTriangle {...iconProps} />;
    case 'explore': return <Compass {...iconProps} />;
    case 'evidence': return <Search {...iconProps} />;
    case 'reframe': return <RefreshCw {...iconProps} />;
    default: return <HelpCircle {...iconProps} />;
  }
}

// 苏格拉底提问卡片
function SocraticQuestionCard({ question, index }: { question: Question; index: number }) {
  const config = QUESTION_TYPE_CONFIG[question.type];

  return (
    <div className="socratic-card mb-2 last:mb-0">
      <div className="flex items-start gap-2">
        <div
          className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5"
          style={{ backgroundColor: `${config.color}15`, color: config.color }}
        >
          <span className="text-xs font-bold">{index + 1}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <QuestionTypeIcon type={question.type} />
            <span
              className="text-[11px] font-medium px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: `${config.color}12`,
                color: config.color,
              }}
            >
              {config.label}
            </span>
          </div>
          <p className="text-sm text-text leading-relaxed">{question.question}</p>
          {question.purpose && (
            <p className="text-[11px] text-text-muted mt-1 italic">
              {question.purpose}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// AI消息组件
function AIMessageBubble({ message, isLatest }: { message: Message; isLatest?: boolean }) {
  const [showThinking, setShowThinking] = useState(false);
  const [displayContent, setDisplayContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const contentRef = useRef(message.content);
  const typingIndexRef = useRef(0);

  // 打字机效果 - 只在消息最新且刚收到时触发
  useEffect(() => {
    if (!message.content || !isLatest) {
      setDisplayContent(message.content);
      return;
    }

    // 如果内容已经完整显示，不再重新打字
    if (displayContent === message.content) {
      return;
    }

    // 开始打字效果
    setIsTyping(true);
    typingIndexRef.current = 0;
    contentRef.current = message.content;

    const typeNextChar = () => {
      const fullContent = contentRef.current;
      if (typingIndexRef.current < fullContent.length) {
        // 每次显示2-3个字符，加速效果
        const chunkSize = Math.random() > 0.5 ? 3 : 2;
        typingIndexRef.current = Math.min(
          typingIndexRef.current + chunkSize,
          fullContent.length
        );
        setDisplayContent(fullContent.substring(0, typingIndexRef.current));
        // 动态间隔，模拟真实打字节奏
        const delay = 15 + Math.random() * 25;
        setTimeout(typeNextChar, delay);
      } else {
        setIsTyping(false);
      }
    };

    const timer = setTimeout(typeNextChar, 50);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message.content]);

  // 消息内容变化时更新显示
  useEffect(() => {
    if (!isLatest) {
      setDisplayContent(message.content);
    }
  }, [message.content, isLatest]);

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 简单的Markdown渲染
  const renderMarkdown = (text: string) => {
    if (!text) return null;

    const lines = text.split('\n');
    const elements: JSX.Element[] = [];
    let inList = false;
    let listItems: string[] = [];
    let listKey = 0;

    const flushList = () => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`list-${listKey++}`} className="list-disc pl-5 mb-2 space-y-0.5">
            {listItems.map((item, i) => (
              <li key={i} className="text-sm leading-relaxed">{item}</li>
            ))}
          </ul>
        );
        listItems = [];
        inList = false;
      }
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();

      // 标题
      if (trimmed.startsWith('### ')) {
        flushList();
        elements.push(
          <h3 key={idx} className="text-base font-semibold text-primary mt-3 mb-1.5">
            {trimmed.slice(4)}
          </h3>
        );
        return;
      }
      if (trimmed.startsWith('## ')) {
        flushList();
        elements.push(
          <h2 key={idx} className="text-lg font-semibold text-primary mt-4 mb-2">
            {trimmed.slice(3)}
          </h2>
        );
        return;
      }
      if (trimmed.startsWith('# ')) {
        flushList();
        elements.push(
          <h1 key={idx} className="text-xl font-bold text-primary mt-4 mb-2">
            {trimmed.slice(2)}
          </h1>
        );
        return;
      }

      // 引用
      if (trimmed.startsWith('> ')) {
        flushList();
        elements.push(
          <blockquote key={idx} className="border-l-2 border-accent pl-3 my-2 italic text-text-muted text-sm">
            {trimmed.slice(2)}
          </blockquote>
        );
        return;
      }

      // 列表项
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        inList = true;
        const itemText = trimmed.slice(2);
        // 处理粗体
        const formatted = itemText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        listItems.push(formatted);
        return;
      }

      // 非列表项，刷新列表
      if (inList && !trimmed.startsWith('- ') && !trimmed.startsWith('* ')) {
        flushList();
      }

      // 空行
      if (trimmed === '') {
        flushList();
        return;
      }

      // 普通段落（处理粗体）
      flushList();
      const parts = line.split(/(\*\*.*?\*\*)/g);
      elements.push(
        <p key={idx} className="text-sm leading-relaxed mb-1.5">
          {parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="text-primary font-semibold">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return <span key={pIdx}>{part}</span>;
          })}
        </p>
      );
    });

    flushList();
    return elements;
  };

  return (
    <div className="flex gap-3 message-appear">
      {/* AI头像 */}
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center shadow-soft">
        <BookOpen className="w-4 h-4 text-white" />
      </div>

      {/* 消息内容 */}
      <div className="flex-1 min-w-0">
        {/* 头部 */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-semibold text-primary">教员</span>
          <span className="text-[11px] text-text-muted flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatTime(message.timestamp)}
          </span>
        </div>

        {/* 思考过程（可折叠） */}
        {message.thinking && (
          <div className="mb-2">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center gap-1 text-xs text-text-muted hover:text-primary transition-colors py-1"
            >
              <Lightbulb className="w-3.5 h-3.5" />
              <span>思考过程</span>
              {showThinking ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>
            {showThinking && (
              <div className="thinking-section mt-1 px-3 py-2">
                <p className="text-xs text-text-muted leading-relaxed whitespace-pre-wrap">
                  {message.thinking}
                </p>
              </div>
            )}
          </div>
        )}

        {/* 苏格拉底提问 */}
        {message.questions && message.questions.length > 0 && (
          <div className="mb-2">
            <div className="flex items-center gap-1.5 mb-2">
              <HelpCircle className="w-4 h-4 text-secondary-dark" />
              <span className="text-xs font-medium text-secondary-dark">
                苏格拉底提问
              </span>
            </div>
            {message.questions.map((q, i) => (
              <SocraticQuestionCard key={i} question={q} index={i} />
            ))}
          </div>
        )}

        {/* 主要内容 */}
        <div className="bg-surface rounded-bubble-lg rounded-tl-sm px-4 py-3 shadow-soft border border-border relative overflow-hidden">
          {/* 左侧棕色竖线装饰 */}
          <div className="absolute left-0 top-2 bottom-2 w-[3px] bg-primary/20 rounded-full" />

          <div className={`markdown-content ${isTyping ? 'typing-cursor' : ''}`}>
            {renderMarkdown(displayContent)}
          </div>

          {/* 打字中指示器 */}
          {isTyping && (
            <div className="flex items-center gap-1 mt-2 text-text-muted">
              <div className="flex gap-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse" style={{ animationDelay: '0.2s' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-pulse" style={{ animationDelay: '0.4s' }} />
              </div>
              <span className="text-[11px]">正在思考...</span>
            </div>
          )}
        </div>

        {/* 毛选引用 */}
        {message.references && message.references.length > 0 && (
          <div className="mt-2 quote-section">
            <div className="flex items-center gap-1 mb-1">
              <BookOpen className="w-3 h-3 text-text-muted" />
              <span className="text-[11px] text-text-muted">相关引用</span>
            </div>
            {message.references.map((ref, i) => (
              <p key={i} className="text-[11px] text-text-muted italic leading-relaxed">
                「{ref}」
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// 用户消息组件
function UserMessageBubble({ message }: { message: Message }) {
  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex gap-3 flex-row-reverse message-appear">
      {/* 用户头像 */}
      <div className="shrink-0 w-8 h-8 rounded-full bg-accent flex items-center justify-center shadow-soft">
        <User className="w-4 h-4 text-white" />
      </div>

      {/* 消息内容 */}
      <div className="flex-1 min-w-0 flex flex-col items-end">
        {/* 头部 */}
        <div className="flex items-center gap-2 mb-1.5 flex-row-reverse">
          <span className="text-sm font-semibold text-text">你</span>
          <span className="text-[11px] text-text-muted flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatTime(message.timestamp)}
          </span>
        </div>

        {/* 消息气泡 */}
        <div className="bg-[#E3F2FD] dark:bg-[#1a3050] rounded-bubble-lg rounded-tr-sm px-4 py-3 shadow-soft max-w-[85%] md:max-w-[75%]">
          <p className="text-sm text-[#1565C0] dark:text-[#90CAF9] leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>
      </div>
    </div>
  );
}

export function MessageBubble({ message, isLatest }: MessageBubbleProps) {
  if (message.role === 'user') {
    return <UserMessageBubble message={message} />;
  }

  return <AIMessageBubble message={message} isLatest={isLatest} />;
}
