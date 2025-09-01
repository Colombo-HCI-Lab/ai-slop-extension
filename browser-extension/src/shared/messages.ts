// Message contracts and enums shared between content and background

export enum MessageType {
  AiSlopRequest = 'AI_SLOP_REQUEST',
  ChatRequest = 'CHAT_REQUEST',
  ChatHistoryRequest = 'CHAT_HISTORY_REQUEST',
  ToggleChatWindow = 'TOGGLE_CHAT_WINDOW',
  AnalyticsEventsBatch = 'ANALYTICS_EVENTS_BATCH',
  UserInit = 'USER_INIT',
  SessionInit = 'SESSION_INIT',
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

export type AnalyticsEventsBatch = {
  type: MessageType.AnalyticsEventsBatch;
  events: Array<{
    event_type: string;
    event_category: 'session' | 'post' | 'chat' | 'interaction' | 'performance';
    user_id?: string;
    post_id?: string;
    session_id?: string;
    event_data: Record<string, unknown>;
    client_timestamp: string;
  }>;
};

export type UserInit = {
  type: MessageType.UserInit;
  timezone: string;
  locale: string;
  browserInfo: Record<string, unknown>;
};

export type SessionInit = {
  type: MessageType.SessionInit;
  userId: string;
  browserInfo?: Record<string, unknown>;
  timezone?: string;
  locale?: string;
};

// Session start/end messages removed (handled client-side via analytics events)

export type AnyMessage =
  | AiSlopRequest
  | ChatRequest
  | ChatHistoryRequest
  | ToggleChatWindow
  | AnalyticsEventsBatch
  | UserInit
  | SessionInit;

export const isMessage = (msg: unknown): msg is AnyMessage =>
  !!msg && typeof msg === 'object' && msg !== null && 'type' in (msg as Record<string, unknown>);
