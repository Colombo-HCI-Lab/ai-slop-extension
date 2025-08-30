/**
 * Shared types for the browser extension
 */

export interface MetricsConfig {
  batchSize: number;
  flushInterval: number;
  enableDebugLogging: boolean;
  privacyMode: 'strict' | 'balanced' | 'full';
}

export interface AnalyticsEvent {
  type: string;
  category: string;
  value?: number;
  label?: string;
  metadata?: Record<string, unknown>;
  clientTimestamp: string;
}

export interface ScrollMetrics {
  totalDistance: number;
  pauseCount: number;
  primaryDirection: 'up' | 'down';
  averageSpeed: number;
}

export interface PostTrackingData {
  firstSeen: number;
  element: Element;
  hasIcon: boolean;
  interacted: boolean;
  iconVisibleDuration?: number;
  lastInteraction?: string;
}

export interface UserSession {
  userId: string;
  sessionId: string;
  startTime: number;
  lastActivity: number;
}

export interface ChatSession {
  id: string;
  postId: string;
  userId: string;
  startTime: number;
  messageCount: number;
  suggestedQuestionsUsed: number;
}

// Unified analytics event for backend consolidation
export interface UnifiedAnalyticsEvent {
  event_type: string;
  event_category: 'session' | 'post' | 'chat' | 'interaction' | 'performance';
  user_id?: string;
  post_id?: string;
  session_identifier?: string;
  event_data: Record<string, unknown>;
  client_timestamp: string; // ISO
}

export interface EventBatchRequest {
  events: UnifiedAnalyticsEvent[];
}
