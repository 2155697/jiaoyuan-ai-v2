/**
 * 教员AI顾问 - 类型定义
 */

/** 消息角色 */
export type MessageRole = 'user' | 'assistant';

/** 提问类型 - 苏格拉底提问分类 */
export type QuestionType = 'clarify' | 'challenge' | 'explore' | 'evidence' | 'reframe';

/** 流式消息块类型 */
export type StreamChunkType = 'thinking' | 'content' | 'questions' | 'references' | 'done' | 'progress' | 'thinking_chunk' | 'error';

/** 苏格拉底提问 */
export interface Question {
  question: string;
  type: QuestionType;
  purpose: string;
}

/** 聊天消息 */
export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  thinking?: string;
  questions?: Question[];
  references?: string[];
  timestamp: Date;
}

/** 流式消息块 */
export interface StreamChunk {
  type: StreamChunkType;
  content: string;
  questions?: Question[];
  references?: string[];
  // 进度信息
  step?: number;
  total?: number;
  percent?: number;
  label?: string;
  detail?: string;
}

/** 进度状态 */
export interface ProgressState {
  step: number;
  total: number;
  percent: number;
  label: string;
  detail: string;
}

/** WebSocket发送的消息 */
export interface WebSocketSendMessage {
  message: string;
  session_id: string;
  user_id: string;
}

/** WebSocket接收的消息 */
export interface WebSocketReceiveMessage {
  type: StreamChunkType;
  content: string;
  questions?: Question[];
  references?: string[];
}

/** 会话 */
export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

/** 认知状态 - 六步循环 */
export interface CognitiveState {
  goal: string;      // 目标识别
  plan: string;      // 方案设计
  link: string;      // 环节定位
  need: string;      // 需求分析
  factor: string;    // 因素评估
  evaluate: string;  // 评估反馈
}

/** 系统状态 */
export interface SystemStatus {
  connected: boolean;
  modelLoaded: boolean;
  lastPing: number;
}

/** 快捷提示 */
export interface QuickPrompt {
  label: string;
  prompt: string;
  icon: string;
}

/** 提问类型配置 */
export const QUESTION_TYPE_CONFIG: Record<QuestionType, { label: string; color: string; icon: string }> = {
  clarify: {
    label: '澄清',
    color: '#3498DB',
    icon: 'HelpCircle',
  },
  challenge: {
    label: '挑战',
    color: '#E74C3C',
    icon: 'AlertTriangle',
  },
  explore: {
    label: '探索',
    color: '#27AE60',
    icon: 'Compass',
  },
  evidence: {
    label: '求证',
    color: '#F39C12',
    icon: 'Search',
  },
  reframe: {
    label: '重构',
    color: '#9B59B6',
    icon: 'RefreshCw',
  },
};

/** 快捷提示预设 */
export const QUICK_PROMPTS: QuickPrompt[] = [
  { label: '帮我分析矛盾', prompt: '请帮我分析当前面临的主要矛盾是什么', icon: 'GitBranch' },
  { label: '判断阶段', prompt: '请帮我判断当前处于什么阶段，主要任务是什么', icon: 'MapPin' },
  { label: '分析形势', prompt: '请帮我分析当前的形势，有哪些有利和不利因素', icon: 'BarChart3' },
  { label: '制定策略', prompt: '请帮我制定斗争策略，如何团结朋友、孤立敌人', icon: 'Target' },
  { label: '调查研究', prompt: '我应该如何进行调查研究，了解真实情况', icon: 'Search' },
  { label: '总结经验', prompt: '请帮我总结历史经验，提炼规律性的认识', icon: 'BookOpen' },
];
