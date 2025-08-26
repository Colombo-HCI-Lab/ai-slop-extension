// Message contracts and enums shared between content and background

export enum MessageType {
  AiSlopRequest = 'AI_SLOP_REQUEST',
  ChatRequest = 'CHAT_REQUEST',
  ChatHistoryRequest = 'CHAT_HISTORY_REQUEST',
  ToggleChatWindow = 'TOGGLE_CHAT_WINDOW',
  MetricsBatch = 'METRICS_BATCH',
}

export type AiSlopRequest = {
  type: MessageType.AiSlopRequest;
  content: string;
  postId: string;
  imageUrls?: string[];
  videoUrls?: string[];
  postUrl?: string;
  hasVideos?: boolean;
  // passthrough for any preprocessed video results
  videoResults?: unknown;
};

export type ChatRequest = {
  type: MessageType.ChatRequest;
  postId: string;
  message: string;
  userId: string;
  postContent?: string;
  previousAnalysis?: Record<string, unknown> | null;
};

export type ChatHistoryRequest = {
  type: MessageType.ChatHistoryRequest;
  postId: string;
  userId: string;
};

export type ToggleChatWindow = {
  type: MessageType.ToggleChatWindow;
};

export type MetricsBatch = {
  type: MessageType.MetricsBatch;
  sessionId: string;
  events: Array<{
    type: string;
    category: string;
    value?: number;
    label?: string;
    metadata?: Record<string, unknown>;
    clientTimestamp: string;
  }>;
};

export type AnyMessage = AiSlopRequest | ChatRequest | ChatHistoryRequest | ToggleChatWindow | MetricsBatch;

export const isMessage = (msg: unknown): msg is AnyMessage =>
  !!msg && typeof msg === 'object' && msg !== null && 'type' in (msg as Record<string, unknown>);
