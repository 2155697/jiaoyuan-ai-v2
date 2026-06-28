import { useRef, useEffect, useCallback } from 'react';
import { Loader2, Bot, CheckCircle2, Brain, Eye, Lightbulb, MessageSquare, Sparkles } from 'lucide-react';
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

// 5步进度步骤配置
const PROGRESS_STEPS = [
  { key: 1, label: '感知分析', icon: Eye, desc: '分析用户意图和情绪状态' },
  { key: 2, label: '理解问题', icon: Brain, desc: '匹配教员思维框架' },
  { key: 3, label: '深度推理', icon: Lightbulb, desc: '矛盾分析 + 阶段判断' },
  { key: 4, label: '生成回复', icon: Sparkles, desc: '教员风格表达中' },
  { key: 5, label: '完成', icon: MessageSquare, desc: '回复已生成' },
];

function ThinkingIndicator({ progress }: { progress?: ProgressState | null }) {
  const currentStep = progress?.step || 0;
  const currentLabel = progress?.label || '';
  const currentDetail = progress?.detail || '';

  return (
    <div className="flex gap-3 message-appear">
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center shadow-soft">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-semibold text-primary">教员</span>
          {currentStep > 0 && currentStep < 5 && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent/10 text-accent animate-pulse">
              {currentLabel}
            </span>
          )}
        </div>

        {/* 5步进度条 */}
        <div className="bg-surface rounded-xl px-4 py-3 shadow-soft border border-border max-w-xl">
          {/* 步骤进度条 */}
          <div className="flex items-center gap-1 mb-3">
            {PROGRESS_STEPS.map((step, idx) => {
              const isCompleted = currentStep > step.key;
              const isCurrent = currentStep === step.key;
              const StepIcon = step.icon;

              return (
                <div key={step.key} className="flex items-center flex-1">
                  <div className="flex flex-col items-center flex-1">
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-500 ${
                        isCompleted
                          ? 'bg-green-500 text-white'
                          : isCurrent
                          ? 'bg-primary text-white shadow-glow animate-pulse'
                          : 'bg-border text-text-muted'
                      }`}
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 animate-spin-slow" />
                      ) : (
                        <StepIcon className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <span
                      className={`text-[10px] mt-1 transition-colors duration-300 ${
                        isCompleted || isCurrent ? 'text-primary font-medium' : 'text-text-muted'
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                  {idx < PROGRESS_STEPS.length - 1 && (
                    <div
                      className={`h-0.5 flex-1 mx-1 rounded transition-colors duration-500 ${
                        isCompleted ? 'bg-green-400' : 'bg-border'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* 当前步骤详情 */}
          {currentStep > 0 && currentStep < 5 && currentDetail && (
            <div className="thinking-section px-3 py-2 rounded-lg">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-accent status-pulse-green" />
                <span className="text-xs text-text">{currentDetail}</span>
              </div>
            </div>
          )}

          {/* 思考片段流 */}
          {/* thinkingChunks 在 MessageBubble 中显示 */}
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
  }, [messages, isThinking, progress]);

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
        {isThinking && messages[messages.length - 1]?.role === 'user' && <ThinkingIndicator progress={progress} />}
        <div ref={messagesEndRef} className="h-4" />
      </div>
    </div>
  );
}
