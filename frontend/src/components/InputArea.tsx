import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Send,
  Loader2,
  GitBranch,
  MapPin,
  BarChart3,
  Target,
  Search,
  BookOpen,
} from 'lucide-react';
import { QUICK_PROMPTS } from '../types';

interface InputAreaProps {
  onSendMessage: (message: string) => void;
  isThinking: boolean;
  disabled?: boolean;
}

// 快捷提示图标映射
const PROMPT_ICONS: Record<string, React.ReactNode> = {
  GitBranch: <GitBranch className="w-3.5 h-3.5" />,
  MapPin: <MapPin className="w-3.5 h-3.5" />,
  BarChart3: <BarChart3 className="w-3.5 h-3.5" />,
  Target: <Target className="w-3.5 h-3.5" />,
  Search: <Search className="w-3.5 h-3.5" />,
  BookOpen: <BookOpen className="w-3.5 h-3.5" />,
};

export function InputArea({ onSendMessage, isThinking, disabled }: InputAreaProps) {
  const [inputValue, setInputValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整文本框高度
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const maxHeight = 200;
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${newHeight}px`;
  }, []);

  // 监听输入变化调整高度
  useEffect(() => {
    adjustTextareaHeight();
  }, [inputValue, adjustTextareaHeight]);

  // 发送消息
  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed || isThinking || disabled) return;

    onSendMessage(trimmed);
    setInputValue('');

    // 重置文本框高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [inputValue, isThinking, disabled, onSendMessage]);

  // 处理键盘事件
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // 使用快捷提示
  const handleQuickPrompt = useCallback(
    (prompt: string) => {
      if (isThinking || disabled) return;
      onSendMessage(prompt);
    },
    [isThinking, disabled, onSendMessage]
  );

  // 是否可发送
  const canSend = inputValue.trim().length > 0 && !isThinking && !disabled;

  return (
    <div className="shrink-0 bg-surface/80 backdrop-blur-md border-t border-border">
      {/* 快捷提示按钮行 */}
      <div className="px-4 md:px-6 pt-3">
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {QUICK_PROMPTS.map((prompt, index) => (
            <button
              key={index}
              onClick={() => handleQuickPrompt(prompt.prompt)}
              disabled={isThinking || disabled}
              className="quick-prompt-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-background text-xs text-text-muted whitespace-nowrap shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {PROMPT_ICONS[prompt.icon] || <Target className="w-3.5 h-3.5" />}
              <span>{prompt.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 输入区域 */}
      <div className="px-4 md:px-6 pb-3 pt-1">
        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          {/* 文本输入框 */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isThinking
                  ? '教员正在思考中...'
                  : disabled
                  ? '服务未连接，请稍候...'
                  : '描述你面临的问题，回车发送，Shift+回车换行...'
              }
              disabled={isThinking || disabled}
              rows={1}
              className="chat-input w-full px-4 py-3 rounded-xl bg-background resize-none text-sm text-text placeholder:text-text-muted/60 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ maxHeight: '200px', minHeight: '44px' }}
            />
          </div>

          {/* 发送按钮 */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={`send-button flex items-center justify-center w-11 h-11 rounded-xl shrink-0 ${
              canSend
                ? 'bg-accent text-white shadow-glow hover:bg-accent-light'
                : 'bg-border text-text-muted cursor-not-allowed'
            }`}
            title={canSend ? '发送消息' : '请输入内容'}
          >
            {isThinking ? (
              <Loader2 className="w-5 h-5 animate-spin-slow" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* 底部提示 */}
        <div className="flex items-center justify-center gap-2 mt-2 pb-1">
          <p className="text-[10px] text-text-muted/60 text-center">
            {isThinking
              ? '正在运用矛盾分析法进行深度推理...'
              : '教员AI顾问 · 用教员的思维方式帮你分析问题'}
          </p>
        </div>
      </div>
    </div>
  );
}
