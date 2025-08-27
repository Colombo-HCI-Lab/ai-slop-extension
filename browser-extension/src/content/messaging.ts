import {
  MessageType,
  ChatRequest,
  ChatHistoryRequest,
  AiSlopRequest,
  AnalyticsUserInit,
  AnalyticsSessionEnd,
  AnalyticsPostInteraction,
  AnalyticsPerformanceMetric,
  AnalyticsChatSession,
} from '@/shared/messages';
import { AnalyticsEvent } from '@/shared/types';

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

export interface MetricsBatchRequest {
  sessionId: string;
  userId?: string;
  events: AnalyticsEvent[];
}

export async function sendMetricsBatch(request: MetricsBatchRequest): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.MetricsBatch, ...request }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve();
    });
  });
}

export async function initializeAnalyticsUser(payload: Omit<AnalyticsUserInit, 'type'>): Promise<{
  user_id: string;
  session_id: string;
  experiment_groups: string[];
}> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.AnalyticsUserInit, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

export async function endAnalyticsSession(
  payload: Omit<AnalyticsSessionEnd, 'type'>
): Promise<{ status: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.AnalyticsSessionEnd, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}

export async function sendPostInteraction(
  payload: Omit<AnalyticsPostInteraction, 'type'>
): Promise<{ status: string; analytics_id: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: MessageType.AnalyticsPostInteraction, ...payload },
      response => {
        if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
        if (response && response.error) return reject(new Error(response.error));
        resolve(response);
      }
    );
  });
}

export async function recordPerformanceMetric(
  payload: Omit<AnalyticsPerformanceMetric, 'type'>
): Promise<{ status: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: MessageType.AnalyticsPerformanceMetric, ...payload },
      response => {
        if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
        if (response && response.error) return reject(new Error(response.error));
        resolve(response);
      }
    );
  });
}

export async function sendChatSessionMetrics(
  payload: Omit<AnalyticsChatSession, 'type'>
): Promise<{ status: string; session_id: string }> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: MessageType.AnalyticsChatSession, ...payload }, response => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (response && response.error) return reject(new Error(response.error));
      resolve(response);
    });
  });
}
