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
  logger.log('POST', PROCESS_ENDPOINT, { post_id: body.post_id, images: body.image_urls.length, videos: body.video_urls.length, has_videos: body.has_videos });
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
  return fetchJsonWithRetry<ChatResponse>(CHAT_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function getChatHistory(postId: string, userId: string): Promise<ChatHistoryResponse> {
  const url = `${API_BASE_URL}/chat/history/${encodeURIComponent(postId)}?user_id=${encodeURIComponent(userId)}`;
  logger.log('GET', url);
  return fetchJsonWithRetry<ChatHistoryResponse>(url, { method: 'GET' });
}
