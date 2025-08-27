// Message contracts and enums shared between content and background

export enum MessageType {
  AiSlopRequest = 'AI_SLOP_REQUEST',
  ChatRequest = 'CHAT_REQUEST',
  ChatHistoryRequest = 'CHAT_HISTORY_REQUEST',
  ToggleChatWindow = 'TOGGLE_CHAT_WINDOW',
  MetricsBatch = 'METRICS_BATCH',
  AnalyticsUserInit = 'ANALYTICS_USER_INIT',
  AnalyticsSessionEnd = 'ANALYTICS_SESSION_END',
  AnalyticsPostInteraction = 'ANALYTICS_POST_INTERACTION',
  AnalyticsPerformanceMetric = 'ANALYTICS_PERFORMANCE_METRIC',
  AnalyticsChatSession = 'ANALYTICS_CHAT_SESSION',
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
  userId?: string;
  events: Array<{
    type: string;
    category: string;
    value?: number;
    label?: string;
    metadata?: Record<string, unknown>;
    clientTimestamp: string;
  }>;
};

export type AnalyticsUserInit = {
  type: MessageType.AnalyticsUserInit;
  extensionUserId: string;
  timezone: string;
  locale: string;
  browserInfo: Record<string, unknown>;
};

export type AnalyticsSessionEnd = {
  type: MessageType.AnalyticsSessionEnd;
  sessionId: string;
  durationSeconds: number;
  endReason: string;
};

export type AnalyticsPostInteraction = {
  type: MessageType.AnalyticsPostInteraction;
  postId: string;
  userId: string;
  interactionType: string;
  metrics?: {
    backend_response_time_ms?: number;
    time_to_interaction_ms?: number;
    reading_time_ms?: number;
    scroll_depth_percentage?: number;
    viewport_time_ms?: number;
  };
};

export type AnalyticsPerformanceMetric = {
  type: MessageType.AnalyticsPerformanceMetric;
  metricName: string;
  metricValue: number;
  metricUnit?: string;
  endpoint?: string;
  metadata?: Record<string, unknown>;
};

export type AnalyticsChatSession = {
  type: MessageType.AnalyticsChatSession;
  sessionId: string; // chat session token
  userPostAnalyticsId: string;
  durationMs: number;
  messageCount: number;
  userMessageCount: number;
  assistantMessageCount: number;
  suggestedQuestionClicks: number;
  satisfactionRating?: number;
  endedBy?: string;
};

export type AnyMessage =
  | AiSlopRequest
  | ChatRequest
  | ChatHistoryRequest
  | ToggleChatWindow
  | MetricsBatch
  | AnalyticsUserInit
  | AnalyticsSessionEnd
  | AnalyticsPostInteraction
  | AnalyticsPerformanceMetric
  | AnalyticsChatSession;

export const isMessage = (msg: unknown): msg is AnyMessage =>
  !!msg && typeof msg === 'object' && msg !== null && 'type' in (msg as Record<string, unknown>);
