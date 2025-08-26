import { MessageType, ChatRequest, ChatHistoryRequest, AiSlopRequest } from '@/shared/messages';

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
