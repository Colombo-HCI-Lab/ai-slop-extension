/**
 * MetricsCollector - Core analytics collection service for content scripts
 */

import { log, error } from '../../shared/logger';
import { AnalyticsEvent, MetricsConfig, ScrollMetrics, PostTrackingData } from '../../shared/types';
import { sendMetricsBatch } from '../messaging';
import { analytics } from '@/shared/analytics';

export class MetricsCollector {
  private userId: string = '';
  private sessionId: string = '';
  private eventBuffer: AnalyticsEvent[] = [];
  private postVisibilityObserver: IntersectionObserver | null = null;
  private scrollMetrics: ScrollMetrics = {
    totalDistance: 0,
    pauseCount: 0,
    primaryDirection: 'down',
    averageSpeed: 0,
  };
  private performanceObserver: PerformanceObserver | null = null;
  private config: MetricsConfig;
  private flushInterval: number | null = null;
  private lastScrollTime: number = 0;
  private lastScrollY: number = 0;
  private scrollSpeeds: number[] = [];
  private postViewTimes: Map<string, number> = new Map();
  private postCumulativeView: Map<string, number> = new Map();

  // Event throttling and sampling - Reduced rates to minimize analytics volume
  private throttledEvents: Map<string, number> = new Map();
  private samplingRates: Record<string, number> = {
    video_progress: 0.05, // Reduced from 0.2 to 0.05 (5%)
    icon_injected: 0.02, // Reduced from 0.1 to 0.02 (2%)
    icon_injected_fallback: 0.02, // Reduced from 0.1 to 0.02 (2%)
    scroll_behavior: 0.05, // Reduced from 0.3 to 0.05 (5%)
    video_play: 0.1, // Reduced from 0.5 to 0.1 (10%)
    video_pause: 0.1, // Reduced from 0.5 to 0.1 (10%)
    post_view: 0.1, // Added sampling for post views (10%)
    post_viewport_enter: 0.05, // Added sampling (5%)
    post_viewport_exit: 0.05, // Added sampling (5%)
  };
  private eventThrottleTimes: Record<string, number> = {
    video_progress: 30000, // Increased from 10s to 30s
    scroll_behavior: 15000, // Increased from 5s to 15s
    icon_injected: 60000, // Increased from 30s to 60s
    video_play: 5000, // Increased from 2s to 5s
    video_pause: 5000, // Increased from 2s to 5s
    post_viewport_enter: 10000, // Added throttling (10s)
    post_viewport_exit: 10000, // Added throttling (10s)
  };

  // Events to completely skip (too low value for research)
  private skippedEvents: Set<string> = new Set([
    'page_hidden',
    'page_visible',
    'chat_input_focus',
    'chat_input_blur',
    'chat_overlay_drag_start',
    'chat_overlay_drag_end',
  ]);

  constructor(config: MetricsConfig) {
    this.config = config;
    this.initializeObservers();
    this.startAutoFlush();
  }

  public setSession(userId: string, sessionId: string): void {
    this.userId = userId;
    this.sessionId = sessionId;
    log('MetricsCollector session set', { userId, sessionId });
  }

  private initializeObservers(): void {
    try {
      // Initialize intersection observer for post visibility
      this.postVisibilityObserver = new IntersectionObserver(this.handlePostVisibility.bind(this), {
        threshold: [0, 0.25, 0.5, 0.75, 1.0],
        rootMargin: '50px',
      });

      // Performance observer for API timings
      if ('PerformanceObserver' in window) {
        this.performanceObserver = new PerformanceObserver(list => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'measure' && entry.name.startsWith('api-')) {
              this.trackPerformance(entry.name, entry.duration);
            }
          }
        });
        this.performanceObserver.observe({ entryTypes: ['measure'] });
      }

      log('MetricsCollector observers initialized');
    } catch (err) {
      error('Failed to initialize MetricsCollector observers:', err);
    }
  }

  private handlePostVisibility(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      const postId = entry.target.getAttribute('data-post-id');
      if (!postId) return;

      const currentTime = Date.now();

      if (entry.isIntersecting) {
        // Post entered viewport
        this.postViewTimes.set(postId, currentTime);

        // Fire explicit read start
        this.addEvent({
          type: 'post_read_start',
          category: 'interaction',
          metadata: {
            postId,
            intersectionRatio: entry.intersectionRatio,
          },
          clientTimestamp: new Date().toISOString(),
        });

        this.addEvent({
          type: 'post_viewport_enter',
          category: 'interaction',
          value: entry.intersectionRatio,
          metadata: {
            postId,
            intersectionRatio: entry.intersectionRatio,
            boundingRect: {
              width: entry.boundingClientRect.width,
              height: entry.boundingClientRect.height,
            },
          },
          clientTimestamp: new Date().toISOString(),
        });
      } else {
        // Post left viewport
        const startTime = this.postViewTimes.get(postId);
        if (startTime) {
          const viewportTime = currentTime - startTime;
          this.postViewTimes.delete(postId);

          // Update cumulative time
          const prev = this.postCumulativeView.get(postId) || 0;
          const total = prev + viewportTime;
          this.postCumulativeView.set(postId, total);

          this.addEvent({
            type: 'post_viewport_exit',
            category: 'interaction',
            value: viewportTime,
            metadata: {
              postId,
              viewportTimeMs: viewportTime,
            },
            clientTimestamp: new Date().toISOString(),
          });

          // Fire explicit read end with cumulative total so far
          this.addEvent({
            type: 'post_read_end',
            category: 'interaction',
            value: viewportTime,
            metadata: {
              postId,
              sessionViewMs: viewportTime,
              cumulativeViewMs: total,
            },
            clientTimestamp: new Date().toISOString(),
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

  public trackScrollBehavior = this.debounce(
    (scrollData: { scrollY: number; timestamp: number }): void => {
      const { scrollY, timestamp } = scrollData;

      if (this.lastScrollTime > 0) {
        const timeDiff = timestamp - this.lastScrollTime;
        const distanceDiff = Math.abs(scrollY - this.lastScrollY);

        if (timeDiff > 0) {
          const speed = distanceDiff / timeDiff; // pixels per millisecond
          this.scrollSpeeds.push(speed);

          // Keep only recent speeds (last 10)
          if (this.scrollSpeeds.length > 10) {
            this.scrollSpeeds.shift();
          }

          this.scrollMetrics.totalDistance += distanceDiff;
          if (scrollY > this.lastScrollY) {
            this.scrollMetrics.primaryDirection = 'down';
          } else if (scrollY < this.lastScrollY) {
            this.scrollMetrics.primaryDirection = 'up';
          }
        }
      }

      this.lastScrollTime = timestamp;
      this.lastScrollY = scrollY;

      // Report if we have enough data
      if (this.scrollSpeeds.length >= 5) {
        const avgSpeed =
          this.scrollSpeeds.reduce((sum, s) => sum + s, 0) / this.scrollSpeeds.length;
        this.scrollMetrics.averageSpeed = avgSpeed;

        this.addEvent({
          type: 'scroll_behavior',
          category: 'interaction',
          value: avgSpeed,
          metadata: {
            totalDistance: this.scrollMetrics.totalDistance,
            direction: this.scrollMetrics.primaryDirection,
            speedSamples: this.scrollSpeeds.length,
          },
          clientTimestamp: new Date().toISOString(),
        });
      }
    },
    200
  );

  public trackEvent(event: Omit<AnalyticsEvent, 'clientTimestamp'>): void {
    // Apply throttling and sampling filters
    if (!this.shouldLogEvent(event.type)) {
      return;
    }

    const fullEvent: AnalyticsEvent = {
      ...event,
      clientTimestamp: new Date().toISOString(),
    };

    this.addEvent(fullEvent);
  }

  private addEvent(event: AnalyticsEvent): void {
    // Privacy filtering
    if (!this.shouldCollectEvent(event.type)) {
      return;
    }

    const sanitized = this.sanitizeEvent(event);
    this.eventBuffer.push(sanitized);

    // Mirror event to Mixpanel immediately (fire-and-forget)
    try {
      analytics.track(sanitized.type, {
        category: sanitized.category,
        label: sanitized.label,
        value: sanitized.value,
        ...((sanitized.metadata || {}) as Record<string, unknown>),
      });
    } catch {
      // no-op
    }

    // Auto-flush if buffer is full
    if (this.eventBuffer.length >= this.config.batchSize) {
      this.flushEvents();
    }
  }

  public async flushEvents(): Promise<void> {
    if (this.eventBuffer.length === 0) return;

    const events = [...this.eventBuffer];
    this.eventBuffer = [];

    // Fire-and-forget to background; handle failure by re-queuing next cycle
    sendMetricsBatch({ sessionId: this.sessionId, userId: this.userId, events })
      .then(() => {
        log(`Flushed ${events.length} analytics events`);
      })
      .catch(err => {
        error('Failed to send metrics batch:', err);
        // Re-add failed events to buffer (best-effort)
        this.eventBuffer.unshift(...events.slice(0, this.config.batchSize));
      });
  }

  private shouldLogEvent(eventType: string): boolean {
    // Skip completely blocked events
    if (this.skippedEvents.has(eventType)) {
      return false;
    }

    const now = Date.now();

    // Check throttling
    const throttleTime = this.eventThrottleTimes[eventType];
    if (throttleTime) {
      const lastLoggedTime = this.throttledEvents.get(eventType) || 0;
      if (now - lastLoggedTime < throttleTime) {
        return false;
      }
      this.throttledEvents.set(eventType, now);
    }

    // Check sampling
    const samplingRate = this.samplingRates[eventType];
    if (samplingRate && Math.random() > samplingRate) {
      return false;
    }

    return true;
  }

  private trackPerformance(name: string, duration: number): void {
    this.addEvent({
      type: 'performance_timing',
      category: 'performance',
      value: duration,
      label: name,
      metadata: {
        endpoint: name.replace('api-', ''),
        durationMs: duration,
      },
      clientTimestamp: new Date().toISOString(),
    });
  }

  private shouldCollectEvent(eventType: string): boolean {
    // Research mode: Always collect all events
    return true;
  }

  private sanitizeEvent(event: AnalyticsEvent): AnalyticsEvent {
    // Research mode: No sanitization needed, collect all data
    return event;
  }

  private startAutoFlush(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
    }

    this.flushInterval = window.setInterval(() => {
      this.flushEvents();
    }, this.config.flushInterval);
  }

  public destroy(): void {
    if (this.postVisibilityObserver) {
      this.postVisibilityObserver.disconnect();
    }

    if (this.performanceObserver) {
      this.performanceObserver.disconnect();
    }

    if (this.flushInterval) {
      clearInterval(this.flushInterval);
    }

    // Final flush
    this.flushEvents();

    log('MetricsCollector destroyed');
  }

  // Utility functions
  private debounce<T extends (...args: any[]) => void>(func: T, wait: number): T {
    let timeout: number | undefined;

    return ((...args: Parameters<T>) => {
      clearTimeout(timeout);
      timeout = window.setTimeout(() => func.apply(this, args), wait);
    }) as T;
  }

  private throttle<T extends (...args: any[]) => void>(func: T, limit: number): T {
    let inThrottle: boolean;

    return ((...args: Parameters<T>) => {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    }) as T;
  }
}
