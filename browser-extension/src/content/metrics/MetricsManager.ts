/**
 * MetricsManager - Manages metrics collection lifecycle and user session
 */

import { log, error } from '../../shared/logger';
import { MetricsCollector } from './MetricsCollector';
import { MetricsConfig, UserSession } from '../../shared/types';
import { initializeAnalyticsUser, startAnalyticsSession, endAnalyticsSession } from '../messaging';
import { analytics } from '@/shared/analytics';
import { getSessionHiddenTimeoutMs } from '@/shared/env';
import { STORAGE_KEYS } from '@/shared/constants';
import { isInAllowedGroupNow } from '@/content/utils/group';

export class MetricsManager {
  private collector: MetricsCollector | null = null;
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
      // Ensure user and session via backend-generated IDs
      let backendUserId = localStorage.getItem(STORAGE_KEYS.userId) || '';
      let backendSessionId = sessionStorage.getItem(STORAGE_KEYS.sessionId) || '';

      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      const locale = navigator.language || 'en-US';
      const browserInfo = {
        name: 'Chrome',
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
      } as const;

      if (!backendUserId) {
        const res = await initializeAnalyticsUser({
          timezone: tz,
          locale: locale,
          browserInfo: browserInfo as unknown as Record<string, unknown>,
        });
        backendUserId = res.user_id;
        localStorage.setItem(STORAGE_KEYS.userId, backendUserId);
      }

      if (!backendSessionId) {
        const res = await startAnalyticsSession({
          userId: backendUserId,
          browserInfo: browserInfo as unknown as Record<string, unknown>,
        });
        backendSessionId = res.session_id;
        sessionStorage.setItem(STORAGE_KEYS.sessionId, backendSessionId);
      }

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

      this.collector = new MetricsCollector(config);
      this.collector.setSession(backendUserId, backendSessionId);

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
        category: 'navigation',
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

      this.trackEvent({
        type: 'session_start',
        category: 'session',
        metadata: {
          sessionId: backendSessionId,
          userId: backendUserId,
        },
      });

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
    if (!this.collector || !this.session) {
      log('MetricsManager not initialized, skipping event:', event.type);
      return;
    }

    this.updateLastActivity();
    this.collector.trackEvent(event);
  }

  public trackPostView(postId: string, postElement: Element): void {
    if (!this.collector) return;

    // Observe post for viewport tracking
    this.collector.observePost(postElement);

    this.trackEvent({
      type: 'post_view',
      category: 'interaction',
      metadata: {
        postId,
        elementBounds: {
          width: postElement.getBoundingClientRect().width,
          height: postElement.getBoundingClientRect().height,
        },
      },
    });
  }

  public trackPostInteraction(
    postId: string,
    interactionType: string,
    metadata?: Record<string, unknown>
  ): void {
    this.trackEvent({
      type: 'post_interaction',
      category: 'interaction',
      label: interactionType,
      metadata: {
        postId,
        interactionType,
        ...metadata,
      },
    });
  }

  public trackIconInteraction(
    postId: string,
    interactionType: 'click' | 'hover' | 'visible'
  ): void {
    this.trackEvent({
      type: `icon_${interactionType}`,
      category: 'interaction',
      metadata: {
        postId,
        timestamp: Date.now(),
      },
    });
  }

  public trackChatStart(postId: string): void {
    this.trackEvent({
      type: 'chat_start',
      category: 'chat',
      metadata: {
        postId,
        sessionId: this.session?.sessionId,
      },
    });
  }

  public trackDetectionPerformance(
    postId: string,
    processingTimeMs: number,
    verdict: string
  ): void {
    this.trackEvent({
      type: 'detection_performance',
      category: 'performance',
      value: processingTimeMs,
      metadata: {
        postId,
        verdict,
        processingTimeMs,
      },
    });
  }

  public getSession(): UserSession | null {
    return this.session;
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

      // Also tell backend to end the session (fire-and-forget)
      endAnalyticsSession({
        sessionId: this.session.sessionId,
        durationSeconds: Math.round(sessionDuration / 1000),
        endReason: 'page_unload',
      }).catch(e => console.debug('endAnalyticsSession failed', e));
    }

    if (this.collector) {
      void this.collector.flushEvents(); // Final flush (do not block)
      this.collector.destroy();
    }

    this.isInitialized = false;
    log('MetricsManager destroyed');
  }

  private setupNavigationGuards(): void {
    const onLocationChange = async () => {
      if (!isInAllowedGroupNow() && this.session) {
        const duration = Date.now() - this.session.startTime;
        endAnalyticsSession({
          sessionId: this.session.sessionId,
          durationSeconds: Math.round(duration / 1000),
          endReason: 'nav_away',
        }).catch(() => null);
        sessionStorage.removeItem(STORAGE_KEYS.sessionId);
        this.session = null;
      } else if (isInAllowedGroupNow() && !this.session) {
        // Start a new session lazily when navigating into allowed context
        const userId = localStorage.getItem(STORAGE_KEYS.userId);
        if (userId) {
          try {
            const browserInfo = {
              name: 'Chrome',
              userAgent: navigator.userAgent,
              platform: navigator.platform,
              language: navigator.language,
            } as const;
            const res = await startAnalyticsSession({
              userId,
              browserInfo: browserInfo as unknown as Record<string, unknown>,
            });
            const newSessionId = res.session_id;
            sessionStorage.setItem(STORAGE_KEYS.sessionId, newSessionId);
            this.session = {
              userId,
              sessionId: newSessionId,
              startTime: Date.now(),
              lastActivity: Date.now(),
            };
            if (this.collector) this.collector.setSession(userId, newSessionId);
            analytics.registerSuper({ session_id: newSessionId });
          } catch {}
        }
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
            const duration = Date.now() - this.session.startTime;
            endAnalyticsSession({
              sessionId: this.session.sessionId,
              durationSeconds: Math.round(duration / 1000),
              endReason: 'tab_hidden_timeout',
            }).catch(() => null);
            sessionStorage.removeItem(STORAGE_KEYS.sessionId);
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
      if (!this.collector) return;

      this.updateLastActivity();

      if (!ticking) {
        requestAnimationFrame(() => {
          this.collector?.trackScrollBehavior({
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
