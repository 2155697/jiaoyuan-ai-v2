import { useRef, useEffect, useCallback, useState } from 'react';
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

// 内联动画关键帧
const stripeAnimationStyles = `
  @keyframes stripe-move {
    0% { background-position: 0 0; }
    100% { background-position: 28px 0; }
  }
  @keyframes progress-glow {
    0%, 100% { filter: brightness(1); }
    50% { filter: brightness(1.25); }
  }
  @keyframes icon-breathe {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.08); opacity: 0.85; }
  }
  @keyframes ring-pulse {
    0% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); }
    70% { box-shadow: 0 0 0 6px rgba(139, 92, 246, 0); }
    100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); }
  }
  @keyframes percent-pop {
    0% { transform: scale(1); }
    50% { transform: scale(1.15); }
    100% { transform: scale(1); }
  }
`;

function ThinkingIndicator({ progress }: { progress?: ProgressState | null }) {
  const currentStep = progress?.step || 0;
  const currentLabel = progress?.label || '';
  const currentDetail = progress?.detail || '';
  const backendPercent = progress?.percent || 0;

  // 流式生成阶段模拟进度（40% ~ 95%）
  const [simulatedPercent, setSimulatedPercent] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [percentPop, setPercentPop] = useState(false);

  useEffect(() => {
    // 清除旧的定时器
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // 如果后端进度 >= 100，直接使用
    if (backendPercent >= 100) {
      setSimulatedPercent(100);
      return;
    }

    // 如果后端进度 <= 40，直接使用后端进度
    if (backendPercent <= 40) {
      setSimulatedPercent(backendPercent);
    }

    // 在流式生成阶段（step 4，后端给40%），模拟增长到95%
    if (currentStep === 4 && backendPercent >= 40 && backendPercent < 100) {
      setSimulatedPercent(backendPercent);
      timerRef.current = setInterval(() => {
        setSimulatedPercent(prev => {
          if (prev >= 95) return 95;
          // 每100ms增长约0.5%，10秒从40%到95%
          const next = prev + 0.5;
          return next > 95 ? 95 : next;
        });
      }, 100);
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [currentStep, backendPercent]);

  // 显示用的百分比：优先使用模拟进度，但如果后端给更高值则使用后端值
  const displayPercent = backendPercent >= 100 ? 100 : Math.max(simulatedPercent, backendPercent);
  const isComplete = displayPercent >= 100;

  // 百分比变化时触发动画（必须在 displayPercent 声明之后）
  const roundedPercent = Math.round(displayPercent);
  useEffect(() => {
    setPercentPop(true);
    const timer = setTimeout(() => setPercentPop(false), 200);
    return () => clearTimeout(timer);
  }, [roundedPercent]);

  return (
    <div className="flex gap-3 message-appear">
      {/* 注入动画关键帧 */}
      <style dangerouslySetInnerHTML={{ __html: stripeAnimationStyles }} />

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

        {/* 5步进度条 + 百分比进度条 */}
        <div className="bg-surface rounded-xl px-4 py-3 shadow-medium border border-border/80 max-w-xl relative overflow-hidden">
          {/* 顶部微光装饰线 */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

          {/* 百分比进度条 */}
          {currentStep > 0 && currentStep < 5 && (
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] text-text-muted font-medium tracking-wide">思考进度</span>
                <span
                  className={`text-sm font-bold font-mono tabular-nums transition-colors duration-300 ${
                    isComplete ? 'text-green-500' : 'text-primary'
                  }`}
                  style={{
                    animation: percentPop ? 'percent-pop 0.2s ease-out' : 'none',
                    textShadow: isComplete ? '0 0 8px rgba(34,197,94,0.3)' : '0 0 6px rgba(139,92,246,0.2)',
                  }}
                >
                  {Math.round(displayPercent)}%
                </span>
              </div>
              <div className="h-2.5 bg-border/70 rounded-full overflow-hidden shadow-inner">
                <div
                  className="h-full rounded-full transition-all duration-300 ease-out relative"
                  style={{
                    width: `${Math.min(displayPercent, 100)}%`,
                    background: isComplete
                      ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                      : 'linear-gradient(90deg, #8b5cf6, #a78bfa, #c4b5fd)',
                    backgroundSize: '28px 28px',
                    animation: isComplete
                      ? 'progress-glow 1.5s ease-in-out 2'
                      : 'stripe-move 0.8s linear infinite, progress-glow 2s ease-in-out infinite',
                    boxShadow: isComplete
                      ? '0 0 12px rgba(34,197,94,0.4)'
                      : '0 0 10px rgba(139,92,246,0.35)',
                  }}
                >
                  {/* 条纹叠加层 */}
                  {!isComplete && (
                    <div
                      className="absolute inset-0 rounded-full"
                      style={{
                        backgroundImage:
                          'repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(255,255,255,0.18) 6px, rgba(255,255,255,0.18) 12px)',
                        backgroundSize: '28px 28px',
                      }}
                    />
                  )}
                  {/* 完成时的闪光效果 */}
                  {isComplete && (
                    <div
                      className="absolute inset-0 rounded-full"
                      style={{
                        backgroundImage:
                          'repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(255,255,255,0.12) 6px, rgba(255,255,255,0.12) 12px)',
                        backgroundSize: '28px 28px',
                        animation: 'stripe-move 0.8s linear infinite',
                      }}
                    />
                  )}
                </div>
              </div>
            </div>
          )}

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
                          ? 'bg-primary text-white animate-pulse'
                          : 'bg-border text-text-muted'
                      }`}
                      style={
                        isCurrent
                          ? {
                              animation: 'ring-pulse 1.8s ease-out infinite',
                              boxShadow: '0 0 0 0 rgba(139, 92, 246, 0.4)',
                            }
                          : isCompleted
                          ? { boxShadow: '0 0 6px rgba(34,197,94,0.3)' }
                          : undefined
                      }
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 animate-spin-slow" style={{ animation: 'icon-breathe 1.5s ease-in-out infinite, spin 2.5s linear infinite' }} />
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
                      className={`h-0.5 flex-1 mx-1 rounded transition-all duration-500 ${
                        isCompleted ? 'bg-green-400 shadow-[0_0_4px_rgba(34,197,94,0.3)]' : 'bg-border'
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
