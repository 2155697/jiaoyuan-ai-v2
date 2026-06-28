import { useState, useEffect } from 'react';
import { BookOpen, Wifi, WifiOff, Menu, X } from 'lucide-react';

interface HeaderProps {
  isConnected: boolean;
  onMenuClick?: () => void;
  sidebarOpen?: boolean;
}

export function Header({ isConnected, onMenuClick, sidebarOpen }: HeaderProps) {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const timeStr = currentTime.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <header className="shrink-0 bg-surface/80 backdrop-blur-md border-b border-border relative z-20">
      {/* 顶部红线装饰 */}
      <div className="h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent" />

      <div className="flex items-center justify-between px-4 md:px-6 py-3">
        {/* 左侧：菜单按钮 + 标题 */}
        <div className="flex items-center gap-3">
          {/* 移动端菜单按钮 */}
          <button
            onClick={onMenuClick}
            className="md:hidden p-1.5 rounded-lg hover:bg-primary/5 transition-colors"
            aria-label="切换侧边栏"
          >
            {sidebarOpen ? (
              <X className="w-5 h-5 text-text" />
            ) : (
              <Menu className="w-5 h-5 text-text" />
            )}
          </button>

          {/* Logo + 标题 */}
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center shadow-soft">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1
                className="text-lg md:text-xl font-bold tracking-wide text-text"
                style={{ fontFamily: 'serif' }}
              >
                教员AI顾问
              </h1>
              <p className="hidden sm:block text-[11px] text-text-muted leading-tight">
                用教员的思维方式，帮你分析问题、找到出路
              </p>
            </div>
          </div>
        </div>

        {/* 右侧：状态 + 时间 */}
        <div className="flex items-center gap-3 md:gap-4">
          {/* 连接状态 */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-background border border-border">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-green-500 status-pulse-green'
                  : 'bg-red-500 status-pulse-red'
              }`}
            />
            <span className="text-xs text-text-muted hidden sm:inline">
              {isConnected ? '服务正常' : '连接断开'}
            </span>
            {isConnected ? (
              <Wifi className="w-3.5 h-3.5 text-green-500 sm:hidden" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-red-500 sm:hidden" />
            )}
          </div>

          {/* 时间 */}
          <span className="text-xs text-text-muted font-mono hidden md:block">
            {timeStr}
          </span>
        </div>
      </div>
    </header>
  );
}
