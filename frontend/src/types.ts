export type QuestionType = 'clarify' | 'challenge' | 'explore' | 'evidence' | 'reframe';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  questions?: Question[];
  references?: string[];
  timestamp: Date;
}

export interface Question {
  question: string;
  type: QuestionType;
  purpose: string;
}

export interface StreamChunk {
  type: 'thinking' | 'content' | 'questions' | 'references' | 'done';
  content: string;
  questions?: Question[];
  references?: string[];
}

export interface CognitiveState {
  stage: 'goal' | 'plan' | 'steps' | 'needs' | 'factors' | 'assessment';
  progress: number;
}

export const QUICK_PROMPTS = [
  '帮我分析矛盾',
  '判断当前阶段',
  '分析形势',
  '制定策略',
  '调查研究',
  '总结经验',
];

export const API_BASE = '/api';
export const WS_URL = `ws://${window.location.host}/api/chat/ws`;

// 苏格拉底提问类型配置
export const QUESTION_TYPE_CONFIG: Record<QuestionType, { label: string; color: string }> = {
  clarify: { label: '澄清', color: '#4A90D9' },
  challenge: { label: '挑战', color: '#E67E22' },
  explore: { label: '探索', color: '#27AE60' },
  evidence: { label: '求证', color: '#8E44AD' },
  reframe: { label: '重构', color: '#C0392B' },
};
