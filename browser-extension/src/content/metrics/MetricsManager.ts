/**
 * MetricsManager - Manages metrics collection lifecycle and user session
 */

import { log, error } from '../../shared/logger';
import { AnalyticsEventCollector } from './AnalyticsEventCollector';
import { ComprehensiveAnalyticsManager } from './ComprehensiveAnalyticsManager';
import { MetricsConfig, UserSession } from '../../shared/types';
import { verifyAndInitializeUserSession } from '../utils/initialization';
import { analytics } from '@/shared/analytics';
import { getSessionHiddenTimeoutMs } from '@/shared/env';
import { isInAllowedGroupNow } from '@/content/utils/group';

export class MetricsManager {
  private rawCollector: AnalyticsEventCollector | null = null;
  private comprehensiveAnalytics: ComprehensiveAnalyticsManager | null = null;
  private session: UserSession | null = null;
  private isInitialized: boolean = false;
  private hiddenTimer: number | null = null;

  private readonly defaultConfig: MetricsConfig = {
    batchSize: 50, // Increased from 25 to 50 - batch more events together
    flushInterval: 60000, // Increased from 30s to 60s - flush less frequently
    enableDebugLogging: false, // Will be overridden by environment
    privacyMode: 'full', // Research mode: Full data collection
  };

  public async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      // CRITICAL: Verify and initialize user/session BEFORE any analytics or post processing
      const { userId: backendUserId, sessionId: backendSessionId, isNewUser, isNewSession } = 
        await verifyAndInitializeUserSession();
      
      log('User/Session verified and initialized', { 
        userId: backendUserId, 
        sessionId: backendSessionId,
        isNewUser,
        isNewSession 
      });

      this.session = {
        userId: backendUserId,
        sessionId: backendSessionId,
        startTime: Date.now(),
        lastActivity: Date.now(),
      };

      // Initialize metrics collector with full data collection
      const config: MetricsConfig = {
        ...this.defaultConfig,
        enableDebugLogging: process.env.NODE_ENV === 'development',
        privacyMode: 'full' as const, // Research mode: Always full collection
      };

      // Initialize analytics event collector (legacy support)
      this.rawCollector = new AnalyticsEventCollector(config);
      this.rawCollector.setSession(backendUserId, backendSessionId);

      // Initialize comprehensive analytics system
      this.comprehensiveAnalytics = new ComprehensiveAnalyticsManager(backendUserId, backendSessionId);

      // Hook Mixpanel identity and super props
      analytics.identify(backendUserId);
      analytics.registerSuper({
        session_id: backendSessionId,
        platform: 'chrome_extension',
        environment: process.env.NODE_ENV || 'production',
      });

      // Lifecycle hooks (teardown on navigation and hidden timeout)
      this.setupNavigationGuards();
      this.setupVisibilityTimeout();

      // Track page load and session start
      this.trackEvent({
        type: 'page_load',
        category: 'interaction',
        metadata: {
          url: window.location.href,
          userAgent: navigator.userAgent,
          viewport: {
            width: window.innerWidth,
            height: window.innerHeight,
          },
          timestamp: new Date().toISOString(),
        },
      });

      // Send session_start analytics event
      const browserInfo = {
        name: 'Chrome',
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
      };
      this.rawCollector.trackSessionStart(browserInfo as unknown as Record<string, unknown>);

      // Set up scroll tracking
      this.setupScrollTracking();

      // Set up page lifecycle tracking
      this.setupPageLifecycle();

      this.isInitialized = true;
      log('MetricsManager initialized', { userId: backendUserId, sessionId: backendSessionId });
    } catch (err) {
      error('Failed to initialize MetricsManager:', err);
    }
  }

  public trackEvent(event: {
    type: string;
    category: string;
    value?: number;
    label?: string;
    metadata?: Record<string, unknown>;
  }): void {
    if (!this.session || !this.rawCollector) {
      log('MetricsManager not initialized, skipping event:', event.type);
      return;
    }

    this.updateLastActivity();
    // Route to unified analytics event collector
    const data: Record<string, unknown> = {
      ...(event.metadata || {}),
    };
    if (typeof event.value !== 'undefined') data.value = event.value;
    if (typeof event.label !== 'undefined') data.label = event.label;
    this.rawCollector.trackEvent(
      event.type,
      event.category as 'session' | 'post' | 'chat' | 'interaction' | 'performance',
      data,
    );
  }

  public trackPostView(postId: string, postElement: Element): void {
    // Legacy analytics (maintain backwards compatibility)
    this.rawCollector?.observePost(postElement);
    this.rawCollector?.trackEvent('post_view', 'post', {
      interaction_type: 'viewed',
      element_bounds: {
        width: postElement.getBoundingClientRect().width,
        height: postElement.getBoundingClientRect().height,
      },
    }, postId);

    // Enhanced comprehensive analytics
    this.comprehensiveAnalytics?.trackPostView(postId, postElement);
  }

  public trackPostInteraction(
    postId: string,
    interactionType: string,
    metadata?: Record<string, unknown>
  ): void {
    // Legacy analytics
    this.rawCollector?.trackPostInteraction(postId, interactionType, {
      ...(metadata || {}),
    });

    // Enhanced analytics - route to appropriate tracker
    if (interactionType === 'chatted') {
      this.comprehensiveAnalytics?.trackChatStart(postId);
    }
  }

  public trackIconInteraction(
    postId: string,
    interactionType: 'click' | 'hover' | 'visible'
  ): void {
    // Consolidated as post_interaction with specific interaction_type
    this.rawCollector?.trackEvent('post_interaction', 'interaction', {
      interaction_type: `icon_${interactionType}`,
      timestamp: Date.now(),
    }, postId);
  }

  public trackChatStart(postId: string): void {
    // Consolidated chat_start (no dedicated session token at this layer)
    this.rawCollector?.trackEvent('chat_start', 'chat', {
      trigger: 'icon_click',
      session_id: this.session?.sessionId,
    }, postId);
  }

  public trackDetectionPerformance(
    postId: string,
    processingTimeMs: number,
    verdict: string
  ): void {
    // Consolidated performance event
    this.rawCollector?.trackEvent('detection_performance', 'performance', {
      post_id: postId,
      processing_time_ms: processingTimeMs,
      verdict,
    });
  }

  public getSession(): UserSession | null {
    return this.session;
  }

  // Enhanced analytics methods
  public trackDetectionResult(
    postId: string, 
    result: 'ai' | 'human' | 'uncertain', 
    confidence: number,
    metadata: Record<string, unknown> = {}
  ): void {
    this.comprehensiveAnalytics?.trackDetectionResult(postId, result, confidence, metadata);
  }

  public trackUserFeedback(
    postId: string, 
    feedback: 'correct' | 'incorrect' | 'uncertain'
  ): void {
    this.comprehensiveAnalytics?.trackUserFeedback(postId, feedback);
  }

  public trackChatMessage(
    sessionId: string, 
    message: string, 
    isUser: boolean, 
    responseTime?: number
  ): void {
    this.comprehensiveAnalytics?.trackChatMessage(sessionId, message, isUser, responseTime);
  }

  public trackUIError(errorType: string, errorMessage: string, context?: any): void {
    this.comprehensiveAnalytics?.trackUIError(errorType, errorMessage, context);
  }

  public trackPerformanceMetric(endpoint: string, responseTime: number, statusCode: number): void {
    this.comprehensiveAnalytics?.trackPerformanceMetric(endpoint, responseTime, statusCode);
  }

  public getAnalyticsSystemHealth(): Record<string, any> {
    return this.comprehensiveAnalytics?.getSystemHealth() || {};
  }

  public async destroy(): Promise<void> {
    if (!this.isInitialized) return;

    if (this.session) {
      const sessionDuration = Date.now() - this.session.startTime;

      this.trackEvent({
        type: 'session_end',
        category: 'session',
        value: sessionDuration,
        metadata: {
          sessionId: this.session.sessionId,
          durationMs: sessionDuration,
          endReason: 'page_unload',
        },
      });

      // No backend session end call; analytics events cover lifecycle
    }

    if (this.rawCollector) {
      // Attempt to record session_end raw event as well
      const duration = this.session ? Date.now() - this.session.startTime : 0;
      this.rawCollector.trackSessionEnd(duration, 'page_unload', {});
      void this.rawCollector.flushEvents();
      this.rawCollector.destroy();
    }

    // Destroy comprehensive analytics system
    if (this.comprehensiveAnalytics) {
      this.comprehensiveAnalytics.destroy();
    }

    this.isInitialized = false;
    log('MetricsManager destroyed');
  }

  private setupNavigationGuards(): void {
    const onLocationChange = async () => {
      // Navigation guard is now simplified - verification happens on next initialize()
      // We don't clear sessions here as the verification flow handles this
      if (!isInAllowedGroupNow()) {
        // If we navigate out of allowed group, clear session
        this.session = null;
      }
    };

    const wrapHistory = (method: 'pushState' | 'replaceState') => {
      type PushReplace = (data: unknown, unused: string, url?: string | URL | null) => unknown;
      const orig = history[method].bind(history) as PushReplace;
      (history as unknown as Record<string, unknown>)[method] = ((
        data: unknown,
        unused: string,
        url?: string | URL | null
      ) => {
        const ret = orig(data, unused, url);
        window.dispatchEvent(new Event('locationchange'));
        return ret as unknown as void;
      }) as History[typeof method];
    };
    wrapHistory('pushState');
    wrapHistory('replaceState');
    window.addEventListener('popstate', () => window.dispatchEvent(new Event('locationchange')));
    window.addEventListener('locationchange', () => void onLocationChange());
  }

  private setupVisibilityTimeout(): void {
    const timeoutMs = getSessionHiddenTimeoutMs();
    const clearTimer = () => {
      if (this.hiddenTimer) {
        clearTimeout(this.hiddenTimer);
        this.hiddenTimer = null;
      }
    };
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        clearTimer();
        this.hiddenTimer = window.setTimeout(() => {
          if (this.session) {
            // Clear session when hidden for too long
            // Session will be re-verified on next initialize()
            this.session = null;
          }
        }, timeoutMs);
      } else {
        clearTimer();
      }
    });
  }

  private setupScrollTracking(): void {
    let ticking = false;

    const handleScroll = () => {
      if (!this.rawCollector) return;

      this.updateLastActivity();

      if (!ticking) {
        requestAnimationFrame(() => {
          this.rawCollector?.trackScrollBehavior({
            scrollY: window.scrollY,
            timestamp: Date.now(),
          });
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
  }

  private setupPageLifecycle(): void {
    // Page visibility tracking removed - low value for analytics

    // Track page unload
    window.addEventListener('beforeunload', () => {
      this.destroy();
    });

    // Track user activity
    const activityEvents = ['click', 'keypress', 'mousemove'];
    activityEvents.forEach(eventType => {
      document.addEventListener(
        eventType,
        () => {
          this.updateLastActivity();
        },
        { passive: true }
      );
    });
  }

  private updateLastActivity(): void {
    if (this.session) {
      this.session.lastActivity = Date.now();
    }
  }

  private getPrivacyMode(): 'strict' | 'balanced' | 'full' {
    // Research mode: Always full data collection
    return 'full';
  }

  // Removed generateSessionId() - now using getSessionId() from storage
}

// Singleton instance for the content script
export const metricsManager = new MetricsManager();
