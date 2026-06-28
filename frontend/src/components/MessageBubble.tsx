import { useState, useRef, useEffect } from 'react';
import {
  ChevronDown, ChevronUp, Lightbulb, HelpCircle, AlertTriangle,
  Compass, Search, RefreshCw, BookOpen, User, Clock,
} from 'lucide-react';
import type { Message, Question, QuestionType, ProgressState } from '../types';
import { QUESTION_TYPE_CONFIG } from '../types';

interface MessageBubbleProps {
  message: Message;
  isLatest?: boolean;
  progress?: ProgressState | null;
  thinkingChunks?: string[];
}

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

function SocraticQuestionCard({ question, index }: { question: Question; index: number }) {
  const config = QUESTION_TYPE_CONFIG[question.type];
  return (
    <div className="socratic-card mb-2 last:mb-0">
      <div className="flex items-start gap-2">
        <div className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center mt-0.5" style={{ backgroundColor: `${config.color}15`, color: config.color }}>
          <span className="text-xs font-bold">{index + 1}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <QuestionTypeIcon type={question.type} />
            <span className="text-[11px] font-medium px-1.5 py-0.5 rounded" style={{ backgroundColor: `${config.color}12`, color: config.color }}>
              {config.label}
            </span>
          </div>
          <p className="text-sm text-text leading-relaxed">{question.question}</p>
          {question.purpose && <p className="text-[11px] text-text-muted mt-1 italic">{question.purpose}</p>}
        </div>
      </div>
    </div>
  );
}

function ThinkingProgress({ progress, thinkingChunks }: { progress: ProgressState | null; thinkingChunks: string[] }) {
  if (!progress) return null;
  const percent = Math.round((progress.step / progress.total) * 100);
  const steps = ['感知分析', '理解问题', '深度推理', '生成回复', '完成'];

  return (
    <div className="mb-3 p-3 bg-[#F5E6D3] dark:bg-[#3d2e1f] rounded-lg border border-[#D4A574] dark:border-[#8B7355]">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium text-[#8B4513] dark:text-[#D4A574]">{progress.label}</span>
        <span className="text-xs text-[#8B7355] dark:text-[#A09080]">({progress.step}/{progress.total})</span>
      </div>
      <div className="w-full h-2 bg-[#E8DDD0] dark:bg-[#5a4a3a] rounded-full overflow-hidden mb-2">
        <div className="h-full bg-gradient-to-r from-[#8B4513] to-[#C0392B] rounded-full transition-all duration-500" style={{ width: `${percent}%` }} />
      </div>
      <div className="flex gap-1 mb-2">
        {steps.map((step, i) => (
          <div key={step} className={`flex-1 h-1 rounded-full transition-colors duration-300 ${i < progress.step ? 'bg-[#8B4513] dark:bg-[#D4A574]' : i === progress.step ? 'bg-[#C0392B] dark:bg-[#E07060]' : 'bg-[#E8DDD0] dark:bg-[#5a4a3a]'}`} />
        ))}
      </div>
      {progress.detail && <p className="text-xs text-[#8B7355] dark:text-[#A09080] italic">{progress.detail}</p>}
      {thinkingChunks.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[#D4A574]/30 dark:border-[#8B7355]/30">
          <p className="text-[10px] font-medium text-[#8B7355] dark:text-[#A09080] mb-1">思考过程：</p>
          <div className="max-h-32 overflow-y-auto space-y-1">
            {thinkingChunks.map((chunk, i) => (
              <p key={i} className="text-[11px] text-[#8B7355] dark:text-[#A09080] leading-relaxed pl-2 border-l-2 border-[#D4A574] dark:border-[#8B7355]">{chunk}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AIMessageBubble({ message, isLatest, progress, thinkingChunks }: { message: Message; isLatest?: boolean; progress?: ProgressState | null; thinkingChunks?: string[] }) {
  const [showThinking, setShowThinking] = useState(false);
  const [displayContent, setDisplayContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const contentRef = useRef(message.content);
  const typingIndexRef = useRef(0);

  useEffect(() => {
    if (!message.content || !isLatest) { setDisplayContent(message.content); return; }
    if (displayContent === message.content) return;
    setIsTyping(true);
    typingIndexRef.current = 0;
    contentRef.current = message.content;
    const typeNextChar = () => {
      const fullContent = contentRef.current;
      if (typingIndexRef.current < fullContent.length) {
        const chunkSize = Math.random() > 0.5 ? 3 : 2;
        typingIndexRef.current = Math.min(typingIndexRef.current + chunkSize, fullContent.length);
        setDisplayContent(fullContent.substring(0, typingIndexRef.current));
        setTimeout(typeNextChar, 15 + Math.random() * 25);
      } else { setIsTyping(false); }
    };
    const timer = setTimeout(typeNextChar, 50);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message.content]);

  useEffect(() => { if (!isLatest) setDisplayContent(message.content); }, [message.content, isLatest]);

  const formatTime = (date: Date) => new Date(date).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  const renderMarkdown = (text: string) => {
    if (!text) return null;
    const lines = text.split('\n');
    const elements: JSX.Element[] = [];
    let inList = false;
    let listItems: string[] = [];
    let listKey = 0;
    const flushList = () => {
      if (listItems.length > 0) {
        elements.push(<ul key={`list-${listKey++}`} className="list-disc pl-5 mb-2 space-y-0.5">{listItems.map((item, i) => <li key={i} className="text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: item }} />)}</ul>);
        listItems = []; inList = false;
      }
    };
    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('### ')) { flushList(); elements.push(<h3 key={idx} className="text-base font-semibold text-primary mt-3 mb-1.5">{trimmed.slice(4)}</h3>); return; }
      if (trimmed.startsWith('## ')) { flushList(); elements.push(<h2 key={idx} className="text-lg font-semibold text-primary mt-4 mb-2">{trimmed.slice(3)}</h2>); return; }
      if (trimmed.startsWith('# ')) { flushList(); elements.push(<h1 key={idx} className="text-xl font-bold text-primary mt-4 mb-2">{trimmed.slice(2)}</h1>); return; }
      if (trimmed.startsWith('> ')) { flushList(); elements.push(<blockquote key={idx} className="border-l-2 border-accent pl-3 my-2 italic text-text-muted text-sm">{trimmed.slice(2)}</blockquote>); return; }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) { inList = true; listItems.push(trimmed.slice(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')); return; }
      if (inList && !trimmed.startsWith('- ') && !trimmed.startsWith('* ')) flushList();
      if (trimmed === '') { flushList(); return; }
      flushList();
      const parts = line.split(/(\*\*.*?\*\*)/g);
      elements.push(<p key={idx} className="text-sm leading-relaxed mb-1.5">{parts.map((part, pIdx) => part.startsWith('**') && part.endsWith('**') ? <strong key={pIdx} className="text-primary font-semibold">{part.slice(2, -2)}</strong> : <span key={pIdx}>{part}</span>)}</p>);
    });
    flushList();
    return elements;
  };

  return (
    <div className="flex gap-3 message-appear">
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center shadow-soft">
        <BookOpen className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-semibold text-primary">教员</span>
          <span className="text-[11px] text-text-muted flex items-center gap-1"><Clock className="w-3 h-3" />{formatTime(message.timestamp)}</span>
        </div>
        {isLatest && progress && progress.step < progress.total && (
          <ThinkingProgress progress={progress} thinkingChunks={thinkingChunks || []} />
        )}
        {message.thinking && (
          <div className="mb-2">
            <button onClick={() => setShowThinking(!showThinking)} className="flex items-center gap-1 text-xs text-text-muted hover:text-primary transition-colors py-1">
              <Lightbulb className="w-3.5 h-3.5" /><span>思考过程</span>{showThinking ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showThinking && <div className="thinking-section mt-1 px-3 py-2"><p className="text-xs text-text-muted leading-relaxed whitespace-pre-wrap">{message.thinking}</p></div>}
          </div>
        )}
        {message.questions && message.questions.length > 0 && (
          <div className="mb-2">
            <div className="flex items-center gap-1.5 mb-2"><HelpCircle className="w-4 h-4 text-secondary-dark" /><span className="text-xs font-medium text-secondary-dark">苏格拉底提问</span></div>
            {message.questions.map((q, i) => <SocraticQuestionCard key={i} question={q} index={i} />)}
          </div>
        )}
        <div className="bg-surface rounded-bubble-lg rounded-tl-sm px-4 py-3 shadow-soft border border-border relative overflow-hidden">
          <div className="absolute left-0 top-2 bottom-2 w-[3px] bg-primary/20 rounded-full" />
          <div className={`markdown-content ${isTyping ? 'typing-cursor' : ''}`}>{renderMarkdown(displayContent)}</div>
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
        {message.references && message.references.length > 0 && (
          <div className="mt-2 quote-section">
            <div className="flex items-center gap-1 mb-1"><BookOpen className="w-3 h-3 text-text-muted" /><span className="text-[11px] text-text-muted">相关引用</span></div>
            {message.references.map((ref, i) => <p key={i} className="text-[11px] text-text-muted italic leading-relaxed">「{ref}」</p>)}
          </div>
        )}
      </div>
    </div>
  );
}

function UserMessageBubble({ message }: { message: Message }) {
  const formatTime = (date: Date) => new Date(date).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return (
    <div className="flex gap-3 flex-row-reverse message-appear">
      <div className="shrink-0 w-8 h-8 rounded-full bg-accent flex items-center justify-center shadow-soft">
        <User className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0 flex flex-col items-end">
        <div className="flex items-center gap-2 mb-1.5 flex-row-reverse">
          <span className="text-sm font-semibold text-text">你</span>
          <span className="text-[11px] text-text-muted flex items-center gap-1"><Clock className="w-3 h-3" />{formatTime(message.timestamp)}</span>
        </div>
        <div className="bg-[#E3F2FD] dark:bg-[#1a3050] rounded-bubble-lg rounded-tr-sm px-4 py-3 shadow-soft max-w-[85%] md:max-w-[75%]">
          <p className="text-sm text-[#1565C0] dark:text-[#90CAF9] leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    </div>
  );
}

export function MessageBubble({ message, isLatest, progress, thinkingChunks }: MessageBubbleProps) {
  if (message.role === 'user') return <UserMessageBubble message={message} />;
  return <AIMessageBubble message={message} isLatest={isLatest} progress={progress} thinkingChunks={thinkingChunks} />;
}
