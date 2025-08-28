import {
  normalizeApiResponse,
  requestAiSlop,
  sendChat,
  getChatHistory,
  sendMetricsBatch as sendMetricsBatchApi,
  initializeUser as initializeUserApi,
  endSession as endSessionApi,
  trackPostInteraction as trackPostInteractionApi,
  recordPerformanceMetric as recordPerformanceMetricApi,
  createOrUpdateChatSession as createOrUpdateChatSessionApi,
} from './api';
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
      sendMetricsBatchApi(message.sessionId, message.events, message.userId)
        .then(() => sendResponse({ status: 'accepted' }))
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.AnalyticsUserInit) {
      logger.log('ANALYTICS_USER_INIT received', { userId: message.userId, sessionId: message.sessionId });
      initializeUserApi({
        user_id: message.userId,
        session_id: message.sessionId,
        timezone: message.timezone,
        locale: message.locale,
        browser_info: message.browserInfo,
        client_ip: null,
      })
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.AnalyticsSessionEnd) {
      logger.log('ANALYTICS_SESSION_END received', {
        sessionId: message.sessionId,
        reason: message.endReason,
      });
      endSessionApi({
        session_id: message.sessionId,
        duration_seconds: message.durationSeconds,
        end_reason: message.endReason,
      })
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.AnalyticsPostInteraction) {
      logger.log('ANALYTICS_POST_INTERACTION received', {
        postId: message.postId,
        type: message.interactionType,
      });
      trackPostInteractionApi(message.postId, {
        user_id: message.userId,
        interaction_type: message.interactionType,
        backend_response_time_ms: message.metrics?.backend_response_time_ms,
        time_to_interaction_ms: message.metrics?.time_to_interaction_ms,
        reading_time_ms: message.metrics?.reading_time_ms,
        scroll_depth_percentage: message.metrics?.scroll_depth_percentage,
        viewport_time_ms: message.metrics?.viewport_time_ms,
      })
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.AnalyticsPerformanceMetric) {
      logger.log('ANALYTICS_PERFORMANCE_METRIC received', { name: message.metricName });
      recordPerformanceMetricApi({
        metric_name: message.metricName,
        metric_value: message.metricValue,
        metric_unit: message.metricUnit,
        endpoint: message.endpoint,
        metadata: message.metadata,
      })
        .then(sendResponse)
        .catch(err => sendResponse({ error: String(err?.message || err) }));
      return true;
    }

    if (message.type === MessageType.AnalyticsChatSession) {
      logger.log('ANALYTICS_CHAT_SESSION received', { chatSessionId: message.sessionId });
      createOrUpdateChatSessionApi({
        session_id: message.sessionId,
        user_post_analytics_id: message.userPostAnalyticsId,
        duration_ms: message.durationMs,
        message_count: message.messageCount,
        user_message_count: message.userMessageCount,
        assistant_message_count: message.assistantMessageCount,
        suggested_question_clicks: message.suggestedQuestionClicks,
        satisfaction_rating: message.satisfactionRating,
        ended_by: message.endedBy,
      })
        .then(sendResponse)
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
