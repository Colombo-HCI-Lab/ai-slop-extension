import { normalizeApiResponse, requestAiSlop, sendChat, getChatHistory, sendMetricsBatch as sendMetricsBatchApi } from './api';
import { clearInFlight, getInFlight, makePostKey, setInFlight } from './state';
import { MessageType, AnyMessage } from '@/shared/messages';
import { createLogger } from '@/shared/logger';

import type { AiSlopResponse } from './api';
const logger = createLogger('bg/messaging');

export function setupBackgroundMessaging(): void {
  chrome.runtime.onMessage.addListener((message: AnyMessage, _sender, sendResponse) => {
    if (!message || !('type' in message)) return;

    if (message.type === MessageType.AiSlopRequest) {
      logger.log('AI_SLOP_REQUEST received', { postId: message.postId });
      const { content, postId, imageUrls, videoUrls, postUrl, hasVideos } = message;
      const key = makePostKey(content, postId, imageUrls, videoUrls, postUrl, hasVideos);
      const existing = getInFlight<AiSlopResponse>(key);
      if (existing) {
        logger.log('De-duplicating in-flight request', { key });
        existing
          .then(sendResponse)
          .catch(err => sendResponse({ error: String(err?.message || err) }));
        return true;
      }

      const reqPromise = requestAiSlop({
        content,
        post_id: postId,
        author: null,
        image_urls: imageUrls || [],
        video_urls: videoUrls || [],
        post_url: postUrl,
        has_videos: hasVideos || false,
      })
        .then(data => normalizeApiResponse(data, postId))
        .finally(() => clearInFlight(key));

      setInFlight(key, reqPromise);
      logger.log('Request dispatched', { key });
      reqPromise
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.ChatRequest) {
      logger.log('CHAT_REQUEST received', { postId: message.postId });
      sendChat({ post_id: message.postId, message: message.message, user_id: message.userId })
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.ChatHistoryRequest) {
      logger.log('CHAT_HISTORY_REQUEST received', { postId: message.postId });
      getChatHistory(message.postId, message.userId)
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.MetricsBatch) {
      logger.log('METRICS_BATCH received', { eventCount: message.events.length });
      sendMetricsBatchApi(message.sessionId, message.events)
        .then(() => sendResponse({ status: 'accepted' }))
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }
  });

  // Toolbar icon click -> toggle chat window in content
  chrome.action.onClicked.addListener(tab => {
    if (tab.url && tab.url.includes('facebook.com') && tab.id) {
      logger.log('Action clicked; toggling chat window', { tabId: tab.id });
      chrome.tabs.sendMessage(tab.id, { type: MessageType.ToggleChatWindow });
    }
  });
}
