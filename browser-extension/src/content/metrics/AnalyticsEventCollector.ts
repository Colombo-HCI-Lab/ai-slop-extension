import { analytics } from '@/shared/analytics';
import type { EventBatchRequest, UnifiedAnalyticsEvent, MetricsConfig, ScrollMetrics } from '@/shared/types';
import { sendAnalyticsEvents } from '../messaging';
import { ComprehensiveAnalyticsManager } from './ComprehensiveAnalyticsManager';

export class AnalyticsEventCollector {
  private eventBuffer: UnifiedAnalyticsEvent[] = [];
  private userId = '';
  private sessionId = '';
  private flushInterval: number | null = null;
  private readonly config: MetricsConfig;

  // Viewport visibility tracking
  private postVisibilityObserver: IntersectionObserver | null = null;
  private postViewTimes: Map<string, number> = new Map();
  private postCumulativeView: Map<string, number> = new Map();

  // Scroll tracking
  private scrollMetrics: ScrollMetrics = {
    totalDistance: 0,
    pauseCount: 0,
    primaryDirection: 'down',
    averageSpeed: 0,
  };
  private lastScrollTime = 0;
  private lastScrollY = 0;
  private scrollSpeeds: number[] = [];

  constructor(config: MetricsConfig) {
    this.config = config;
    this.initializeObservers();
    this.startAutoFlush();
  }

  public setSession(userId: string, sessionId: string): void {
    this.userId = userId;
    this.sessionId = sessionId;
  }

  public trackEvent(
    eventType: string,
    category: 'session' | 'post' | 'chat' | 'interaction' | 'performance',
    data: Record<string, unknown>,
    postId?: string
  ): void {
    const event: UnifiedAnalyticsEvent = {
      event_type: eventType,
      event_category: category,
      user_id: this.userId || undefined,
      post_id: postId,
      session_id: this.sessionId || undefined,
      event_data: data,
      client_timestamp: new Date().toISOString(),
    };

    this.eventBuffer.push(event);

    try {
      analytics.track(eventType, { category, ...data });
    } catch {
      // no-op
    }

    if (this.eventBuffer.length >= this.config.batchSize) this.flushEvents();
  }

  // Session events
  public trackSessionStart(browserInfo: Record<string, unknown>): void {
    this.trackEvent('session_start', 'session', {
      browser_info: browserInfo,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      locale: navigator.language,
      ip_hash: null,
      user_agent: navigator.userAgent,
    });
  }

  public trackSessionEnd(durationMs: number, endReason: string, stats: Record<string, unknown>): void {
    this.trackEvent('session_end', 'session', {
      duration_seconds: Math.round(durationMs / 1000),
      end_reason: endReason,
      posts_viewed: (stats as any).postsViewed || 0,
      posts_analyzed: (stats as any).postsAnalyzed || 0,
      posts_interacted: (stats as any).postsInteracted || 0,
      avg_scroll_speed: (stats as any).avgScrollSpeed || 0,
      total_scroll_distance: (stats as any).totalScrollDistance || 0,
      active_time_seconds: (stats as any).activeTimeSeconds || 0,
      idle_time_seconds: (stats as any).idleTimeSeconds || 0,
    });
  }

  // Post events
  public trackPostView(postId: string, metrics: any): void {
    this.trackEvent(
      'post_view',
      'post',
      {
        interaction_type: 'viewed',
        backend_response_time_ms: metrics.backendResponseTime,
        reading_time_ms: metrics.readingTime,
        scroll_depth_percentage: metrics.scrollDepth,
        viewport_time_ms: metrics.viewportTime,
        first_view: metrics.firstView || false,
        times_viewed: metrics.timesViewed || 1,
      },
      postId,
    );
  }

  public trackPostInteraction(postId: string, interactionType: string, metrics: any): void {
    this.trackEvent(
      'post_interaction',
      'interaction',
      {
        interaction_type: interactionType,
        time_to_interaction_ms: metrics.timeToInteraction,
        icon_visibility_duration_ms: metrics.iconVisibilityDuration,
      },
      postId,
    );
  }

  // Chat events
  public trackChatStart(postId: string, sessionToken: string): void {
    this.trackEvent(
      'chat_start',
      'chat',
      {
        session_token: sessionToken,
        trigger: 'icon_click',
      },
      postId,
    );
  }

  public trackChatMessage(sessionToken: string, messageData: any): void {
    this.trackEvent('chat_message', 'chat', {
      session_token: sessionToken,
      message_count: messageData.messageCount,
      user_messages: messageData.userMessages,
      assistant_messages: messageData.assistantMessages,
      response_time_ms: messageData.responseTime,
      is_user_message: messageData.isUserMessage,
    });
  }

  public trackChatEnd(sessionToken: string, chatStats: any): void {
    this.trackEvent('chat_end', 'chat', {
      session_token: sessionToken,
      duration_ms: chatStats.duration,
      total_messages: chatStats.totalMessages,
      user_message_count: chatStats.userMessageCount,
      assistant_message_count: chatStats.assistantMessageCount,
      suggested_question_clicks: chatStats.suggestedQuestionClicks || 0,
      ended_by: chatStats.endedBy || 'user_close',
      satisfaction_rating: chatStats.satisfactionRating,
      average_response_time_ms: chatStats.avgResponseTime,
      max_response_time_ms: chatStats.maxResponseTime,
    });
  }

  // Performance events
  public trackPerformance(endpoint: string, responseTime: number, statusCode: number): void {
    this.trackEvent('api_response_time', 'performance', {
      endpoint,
      response_time_ms: responseTime,
      status_code: statusCode,
    });
  }

  // --- Viewport tracking ---
  private initializeObservers(): void {
    try {
      this.postVisibilityObserver = new IntersectionObserver(this.handlePostVisibility.bind(this), {
        threshold: [0, 0.25, 0.5, 0.75, 1.0],
        rootMargin: '50px',
      });
    } catch {
      // ignore if unsupported
    }
  }

  private handlePostVisibility(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      const postId = entry.target.getAttribute('data-post-id');
      if (!postId) return;

      const now = Date.now();
      if (entry.isIntersecting) {
        this.postViewTimes.set(postId, now);
        this.trackEvent('post_read_start', 'interaction', {
          post_id: postId,
          intersection_ratio: entry.intersectionRatio,
        });
        this.trackEvent('post_viewport_enter', 'interaction', {
          post_id: postId,
          intersection_ratio: entry.intersectionRatio,
          bounding_rect: {
            width: entry.boundingClientRect.width,
            height: entry.boundingClientRect.height,
          },
        });
      } else {
        const start = this.postViewTimes.get(postId);
        if (start) {
          const viewportTime = now - start;
          this.postViewTimes.delete(postId);

          const prev = this.postCumulativeView.get(postId) || 0;
          const total = prev + viewportTime;
          this.postCumulativeView.set(postId, total);

          this.trackEvent('post_viewport_exit', 'interaction', {
            post_id: postId,
            viewport_time_ms: viewportTime,
          });
          this.trackEvent('post_read_end', 'interaction', {
            post_id: postId,
            session_view_ms: viewportTime,
            cumulative_view_ms: total,
          });
        }
      }
    });
  }

  public observePost(postElement: Element): void {
    if (this.postVisibilityObserver && postElement.getAttribute('data-post-id')) {
      this.postVisibilityObserver.observe(postElement);
    }
  }

  // --- Scroll tracking ---
  public trackScrollBehavior(scrollData: { scrollY: number; timestamp: number }): void {
    const { scrollY, timestamp } = scrollData;
    if (this.lastScrollTime > 0) {
      const dt = timestamp - this.lastScrollTime;
      const dy = Math.abs(scrollY - this.lastScrollY);
      if (dt > 0) {
        const speed = dy / dt;
        this.scrollSpeeds.push(speed);
        if (this.scrollSpeeds.length > 10) this.scrollSpeeds.shift();
        this.scrollMetrics.totalDistance += dy;
        if (scrollY > this.lastScrollY) this.scrollMetrics.primaryDirection = 'down';
        else if (scrollY < this.lastScrollY) this.scrollMetrics.primaryDirection = 'up';
      }
    }
    this.lastScrollTime = timestamp;
    this.lastScrollY = scrollY;

    if (this.scrollSpeeds.length >= 5) {
      const avgSpeed = this.scrollSpeeds.reduce((s, v) => s + v, 0) / this.scrollSpeeds.length;
      this.scrollMetrics.averageSpeed = avgSpeed;
      this.trackEvent('scroll_behavior', 'interaction', {
        average_speed: avgSpeed,
        total_distance: this.scrollMetrics.totalDistance,
        direction: this.scrollMetrics.primaryDirection,
        speed_samples: this.scrollSpeeds.length,
      });
    }
  }

  public async flushEvents(): Promise<void> {
    if (this.eventBuffer.length === 0) return;

    const batch: EventBatchRequest = { events: [...this.eventBuffer] };
    this.eventBuffer = [];
    try {
      await sendAnalyticsEvents(batch);
      // eslint-disable-next-line no-console
      console.log(`Flushed ${batch.events.length} analytics events`);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Failed to send analytics events:', err);
      this.eventBuffer.unshift(
        ...batch.events.slice(0, this.config.batchSize),
      );
    }
  }

  private startAutoFlush(): void {
    if (this.flushInterval) clearInterval(this.flushInterval);
    this.flushInterval = window.setInterval(() => {
      void this.flushEvents();
    }, this.config.flushInterval);
  }

  public destroy(): void {
    if (this.flushInterval) clearInterval(this.flushInterval);
    void this.flushEvents();
  }
}
