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
  type: 'clarify' | 'challenge' | 'explore' | 'evidence' | 'reframe';
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
