/**
 * Enhanced Event Batcher with priority-based queuing and intelligent flushing
 */

import type { UnifiedAnalyticsEvent, EventPriority } from '@/shared/types';
import { createLogger } from '@/shared/logger';
import { sendAnalyticsEvents } from '../messaging';

const logger = createLogger('EnhancedEventBatcher');

interface BatchConfig {
  maxBatchSize: number;
  flushIntervals: Record<EventPriority, number>;
  maxRetries: number;
  retryBackoffBase: number;
}

export class EnhancedEventBatcher {
  private readonly queues: Record<EventPriority, UnifiedAnalyticsEvent[]> = {
    critical: [],
    high: [],
    medium: [],
    low: []
  };

  private readonly timers: Record<EventPriority, number | null> = {
    critical: null,
    high: null,
    medium: null,
    low: null
  };

  private readonly config: BatchConfig = {
    maxBatchSize: 100,
    flushIntervals: {
      critical: 0, // immediate
      high: 5000, // 5 seconds
      medium: 15000, // 15 seconds  
      low: 30000 // 30 seconds
    },
    maxRetries: 3,
    retryBackoffBase: 1000
  };

  private isOnline = navigator.onLine;
  private offlineQueue: UnifiedAnalyticsEvent[] = [];

  constructor() {
    this.setupNetworkListeners();
    this.setupVisibilityHandlers();
  }

  public addEvent(event: UnifiedAnalyticsEvent): void {
    const priority = event.event_priority || this.determinePriority(event);
    
    if (!this.isOnline) {
      this.offlineQueue.push(event);
      return;
    }

    this.queues[priority].push(event);

    // Immediate flush for critical events
    if (priority === 'critical') {
      this.flushQueue('critical');
      return;
    }

    // Check if we need to flush due to size
    if (this.queues[priority].length >= this.config.maxBatchSize) {
      this.flushQueue(priority);
      return;
    }

    // Schedule flush if not already scheduled
    if (!this.timers[priority]) {
      this.scheduleFlush(priority);
    }
  }

  public flushAll(): Promise<void> {
    const flushPromises = Object.keys(this.queues).map(priority => 
      this.flushQueue(priority as EventPriority)
    );
    return Promise.all(flushPromises).then(() => {});
  }

  private determinePriority(event: UnifiedAnalyticsEvent): EventPriority {
    // Critical: errors, performance issues, detection failures
    if (event.event_type.includes('error') || 
        event.event_type.includes('failure') ||
        event.event_category === 'performance' && 
        (event.event_data.status_code as number) >= 500) {
      return 'critical';
    }

    // High: user interactions, detection results, chat events
    if (event.event_category === 'chat' ||
        event.event_type.includes('interaction') ||
        event.event_type.includes('detection') ||
        event.event_type === 'post_view') {
      return 'high';
    }

    // Medium: session events, UI events, content analysis
    if (event.event_category === 'session' ||
        event.event_category === 'ui' ||
        event.event_category === 'content') {
      return 'medium';
    }

    // Low: background metrics, learning analytics
    return 'low';
  }

  private scheduleFlush(priority: EventPriority): void {
    this.timers[priority] = window.setTimeout(() => {
      this.flushQueue(priority);
    }, this.config.flushIntervals[priority]);
  }

  private async flushQueue(priority: EventPriority): Promise<void> {
    if (this.timers[priority]) {
      clearTimeout(this.timers[priority]);
      this.timers[priority] = null;
    }

    const events = this.queues[priority].splice(0, this.config.maxBatchSize);
    if (events.length === 0) return;

    try {
      await this.sendWithRetry(events, 0);
      logger.log(`Flushed ${events.length} ${priority} priority events`);
    } catch (error) {
      logger.error(`Failed to flush ${priority} events after retries:`, error);
      // Re-queue non-critical events for later retry
      if (priority !== 'critical') {
        this.queues[priority].unshift(...events.slice(0, 10)); // Keep only recent ones
      }
    }
  }

  private async sendWithRetry(events: UnifiedAnalyticsEvent[], attempt: number): Promise<void> {
    if (attempt >= this.config.maxRetries) {
      throw new Error(`Max retries (${this.config.maxRetries}) exceeded`);
    }

    try {
      await sendAnalyticsEvents({ events });
    } catch (error) {
      const backoffMs = this.config.retryBackoffBase * Math.pow(2, attempt);
      await this.delay(backoffMs);
      return this.sendWithRetry(events, attempt + 1);
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private setupNetworkListeners(): void {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.processOfflineQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
    });
  }

  private processOfflineQueue(): void {
    if (this.offlineQueue.length === 0) return;

    logger.log(`Processing ${this.offlineQueue.length} offline events`);
    
    // Add offline events back to appropriate queues
    const events = this.offlineQueue.splice(0);
    events.forEach(event => this.addEvent(event));
  }

  private setupVisibilityHandlers(): void {
    // Flush on page visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.flushAll();
      }
    });

    // Flush on page unload
    window.addEventListener('beforeunload', () => {
      this.flushAll();
    });
  }

  public getQueueStats(): Record<EventPriority, number> {
    return {
      critical: this.queues.critical.length,
      high: this.queues.high.length,
      medium: this.queues.medium.length,
      low: this.queues.low.length
    };
  }

  public destroy(): void {
    // Clear all timers
    Object.values(this.timers).forEach(timer => {
      if (timer) clearTimeout(timer);
    });

    // Final flush
    this.flushAll();
  }
}