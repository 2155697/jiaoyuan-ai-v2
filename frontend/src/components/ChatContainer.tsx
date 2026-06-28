import { useRef, useEffect, useCallback } from 'react';
import { Loader2, Bot } from 'lucide-react';
import type { Message, ProgressState } from '../types';
import { MessageBubble } from './MessageBubble';

interface ChatContainerProps {
  messages: Message[];
  isThinking: boolean;
  progress?: ProgressState | null;
  thinkingChunks?: string[];
}

function WelcomeScreen() {
  const features = [
    { title: '矛盾分析', desc: '帮你抓住主要矛盾和矛盾的主要方面' },
    { title: '阶段判断', desc: '分析当前形势，判断所处发展阶段' },
    { title: '调查研究', desc: '提供调查研究方法，了解真实情况' },
    { title: '策略制定', desc: '制定斗争策略，团结朋友、孤立敌人' },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 overflow-y-auto">
      <div className="mb-6">
        <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center shadow-medium mx-auto mb-4">
          <Bot className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-text text-center mb-2" style={{ fontFamily: 'serif' }}>
          教员AI顾问
        </h2>
        <p className="text-sm text-text-muted text-center max-w-md">
          我不是普通的聊天机器人，而是用教员的思维方式，帮你分析问题、找到出路
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {features.map((feature, i) => (
          <div key={i} className="p-4 rounded-xl bg-surface border border-border shadow-soft hover:shadow-medium hover:border-primary/30 transition-all cursor-default group">
            <h3 className="text-sm font-semibold text-primary mb-1 group-hover:text-accent transition-colors">{feature.title}</h3>
            <p className="text-xs text-text-muted leading-relaxed">{feature.desc}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-muted mt-6 text-center">在下方输入框中描述你面临的问题，我会用教员的思想方法帮你分析</p>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex gap-3 message-appear">
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center shadow-soft">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-semibold text-primary">教员</span>
        </div>
        <div className="bg-surface rounded-bubble-lg rounded-tl-sm px-4 py-3 shadow-soft border border-border inline-flex items-center gap-3">
          <Loader2 className="w-4 h-4 text-primary animate-spin-slow" />
          <div className="flex flex-col gap-1">
            <span className="text-sm text-text">正在思考问题...</span>
            <span className="text-[11px] text-text-muted">运用矛盾分析法进行推理</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ChatContainer({ messages, isThinking, progress, thinkingChunks }: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    shouldAutoScroll.current = scrollHeight - scrollTop - clientHeight < 100;
  }, []);

  useEffect(() => {
    if (shouldAutoScroll.current && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isThinking]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, []);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-hidden flex flex-col">
        <WelcomeScreen />
      </div>
    );
  }

  return (
    <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-4 md:px-6 py-4 md:py-6 scroll-smooth">
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            isLatest={index === messages.length - 1 && message.role === 'assistant'}
            progress={index === messages.length - 1 && message.role === 'assistant' ? progress : null}
            thinkingChunks={index === messages.length - 1 && message.role === 'assistant' ? thinkingChunks : []}
          />
        ))}
        {isThinking && messages[messages.length - 1]?.role === 'user' && <ThinkingIndicator />}
        <div ref={messagesEndRef} className="h-4" />
      </div>
    </div>
  );
}
