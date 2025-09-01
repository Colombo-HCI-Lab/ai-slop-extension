import {
  MessageType,
  ChatRequest,
  ChatHistoryRequest,
  AiSlopRequest,
  UserInit,
  SessionInit,
} from '@/shared/messages';
import { EventBatchRequest } from '@/shared/types';

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

export async function sendAiSlopRequest(
  payload: Omit<AiSlopRequest, 'type'>
): Promise<AiSlopResponse> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.AiSlopRequest, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response as AiSlopResponse);
    });
  });
}

export type ChatResponse = {
  id: string;
  message: string;
  suggested_questions: string[];
  context?: Record<string, unknown>;
  timestamp: string;
};

export async function sendChat(
  payload: Omit<ChatRequest, 'type'>
): Promise<ChatResponse | { error: string; details?: string }> {
  return chrome.runtime.sendMessage({ type: MessageType.ChatRequest, ...payload });
}

export async function fetchChatHistory(payload: Omit<ChatHistoryRequest, 'type'>): Promise<{
  messages: Array<{ role: 'user' | 'assistant'; message: string; created_at: string }>;
  total_messages?: number;
}> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.ChatHistoryRequest, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

// Legacy MetricsBatch removed – unified analytics events used instead

// Unified analytics event batch
export async function sendAnalyticsEvents(request: EventBatchRequest): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.AnalyticsEventsBatch, ...request }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve();
    });
  });
}

export async function initializeUser(
  payload: Omit<UserInit, 'type'>
): Promise<{ user_id: string; experiment_groups: string[] }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.UserInit, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

export async function initializeSession(
  payload: Omit<SessionInit, 'type'>
): Promise<{ session_id: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.SessionInit, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

export async function verifyUser(userId: string): Promise<{ valid: boolean; user_id: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.VerifyUser, userId }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

export async function verifySession(
  sessionId: string,
  userId?: string
): Promise<{ valid: boolean; session_id: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.VerifySession, sessionId, userId }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

// Session start/end calls removed – tracked via analytics events only

// Legacy analytics post/metric/chat messages removed – consolidated via analytics events
