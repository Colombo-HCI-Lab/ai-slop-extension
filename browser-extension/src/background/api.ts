import { fetchJsonWithRetry } from '@/shared/net/retry';
import { getApiBase } from '@/shared/env';
import { createLogger } from '@/shared/logger';

export type ApiDetectionResponse = {
  verdict: string;
  confidence: number;
  explanation: string;
  text_ai_probability?: number;
  text_confidence?: number;
  image_ai_probability?: number;
  image_confidence?: number;
  video_ai_probability?: number;
  video_confidence?: number;
  post_id?: string;
  timestamp: string;
};

export type AiSlopResponse = {
  isAiSlop: boolean;
  confidence: number;
  reasoning: string;
  textAiProbability?: number;
  textConfidence?: number;
  imageAiProbability?: number;
  imageConfidence?: number;
  videoAiProbability?: number;
  videoConfidence?: number;
  analysisDetails: Record<string, unknown>;
  processingTime: number;
  timestamp: string;
};

export type ChatHistoryResponse = {
  messages: ChatMessage[];
  total_messages?: number;
};

export type ChatMessage = {
  role: 'user' | 'assistant';
  message: string;
  created_at: string;
};

export type ChatResponse = {
  id: string;
  message: string;
  suggested_questions: string[];
  context?: Record<string, unknown>;
  timestamp: string;
};

const API_BASE_URL = getApiBase();
const logger = createLogger('bg/api');
const PROCESS_ENDPOINT = `${API_BASE_URL}/posts/process`;
const CHAT_ENDPOINT = `${API_BASE_URL}/chat/send`;

export function normalizeApiResponse(data: ApiDetectionResponse, postId: string): AiSlopResponse {
  logger.log('Normalizing detection response', { postId, verdict: data.verdict });
  return {
    isAiSlop: data.verdict === 'ai_slop',
    confidence: data.confidence,
    reasoning: data.explanation,
    textAiProbability: data.text_ai_probability,
    textConfidence: data.text_confidence,
    imageAiProbability: data.image_ai_probability,
    imageConfidence: data.image_confidence,
    videoAiProbability: data.video_ai_probability,
    videoConfidence: data.video_confidence,
    analysisDetails: {
      verdict: data.verdict,
      postId: data.post_id || postId,
    },
    processingTime: 0,
    timestamp: data.timestamp,
  };
}

export async function requestAiSlop(body: {
  content: string;
  post_id: string;
  author: string | null;
  image_urls: string[];
  video_urls: string[];
  post_url?: string;
  has_videos?: boolean;
}): Promise<ApiDetectionResponse> {
  logger.log('POST', PROCESS_ENDPOINT, {
    post_id: body.post_id,
    images: body.image_urls.length,
    videos: body.video_urls.length,
    has_videos: body.has_videos,
  });
  return fetchJsonWithRetry<ApiDetectionResponse>(PROCESS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function sendChat(body: {
  post_id: string;
  message: string;
  user_id: string;
}): Promise<ChatResponse> {
  logger.log('POST', CHAT_ENDPOINT, { post_id: body.post_id });
  return fetchJsonWithRetry<ChatResponse>(
    CHAT_ENDPOINT,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { timeoutMs: 35000, retries: 2, backoffBaseMs: 400 }
  );
}

export async function getChatHistory(postId: string, userId: string): Promise<ChatHistoryResponse> {
  const url = `${API_BASE_URL}/chat/history/${encodeURIComponent(postId)}?user_id=${encodeURIComponent(userId)}`;
  logger.log('GET', url);
  return fetchJsonWithRetry<ChatHistoryResponse>(url, { method: 'GET' });
}

export async function sendMetricsBatch(
  sessionId: string,
  events: Array<{
    type: string;
    category: string;
    value?: number;
    label?: string;
    metadata?: Record<string, unknown>;
    clientTimestamp: string;
  }>,
  userId?: string
): Promise<void> {
  const url = `${API_BASE_URL}/analytics/events/batch`;
  const body = {
    session_id: sessionId,
    user_id: userId,
    events: events,
  };

  logger.log('POST', url, { eventCount: events.length, sessionId });
  await fetchJsonWithRetry<{ status: string }>(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}

// --- Additional Analytics endpoints ---

export async function initializeUser(body: {
  extension_user_id: string;
  browser_info: Record<string, unknown>;
  timezone: string;
  locale: string;
  client_ip?: string | null;
}): Promise<{ user_id: string; session_id: string; experiment_groups: string[] }> {
  const url = `${API_BASE_URL}/analytics/users/initialize`;
  logger.log('POST', url, { extensionUserId: body.extension_user_id });
  return fetchJsonWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}

export async function endSession(body: {
  session_id: string;
  end_reason: string;
  duration_seconds: number;
}): Promise<{ status: string }> {
  const url = `${API_BASE_URL}/analytics/sessions/end`;
  logger.log('POST', url, { sessionId: body.session_id, reason: body.end_reason });
  return fetchJsonWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}

export async function trackPostInteraction(
  postId: string,
  body: {
    user_id: string;
    interaction_type: string;
    backend_response_time_ms?: number;
    time_to_interaction_ms?: number;
    reading_time_ms?: number;
    scroll_depth_percentage?: number;
    viewport_time_ms?: number;
  }
): Promise<{ status: string; analytics_id: string }> {
  const url = `${API_BASE_URL}/analytics/posts/${encodeURIComponent(postId)}/interactions`;
  logger.log('POST', url, { postId, interaction: body.interaction_type });
  return fetchJsonWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}

export async function recordPerformanceMetric(body: {
  metric_name: string;
  metric_value: number;
  metric_unit?: string;
  endpoint?: string;
  metadata?: Record<string, unknown>;
}): Promise<{ status: string }> {
  const url = `${API_BASE_URL}/analytics/performance/metrics`;
  logger.log('POST', url, { name: body.metric_name, value: body.metric_value });
  return fetchJsonWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}

export async function createOrUpdateChatSession(body: {
  session_id: string; // chat session token
  user_post_analytics_id: string;
  duration_ms: number;
  message_count: number;
  user_message_count: number;
  assistant_message_count: number;
  suggested_question_clicks: number;
  satisfaction_rating?: number;
  ended_by?: string;
}): Promise<{ status: string; session_id: string }> {
  const url = `${API_BASE_URL}/analytics/chat/sessions`;
  logger.log('POST', url, {
    chatSessionId: body.session_id,
    analyticsId: body.user_post_analytics_id,
  });
  return fetchJsonWithRetry(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { retries: 3, backoffBaseMs: 500 }
  );
}
