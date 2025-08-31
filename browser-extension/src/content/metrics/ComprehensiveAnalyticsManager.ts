/**
 * Comprehensive Analytics Manager
 * Orchestrates all analytics trackers and provides unified interface
 */

import type { 
  UnifiedAnalyticsEvent, 
  EnhancedMetricsConfig,
  EventPriority
} from '@/shared/types';
import { createLogger } from '@/shared/logger';
import { analytics } from '@/shared/analytics';
import { getSessionHiddenTimeoutMs } from '@/shared/env';

import { EnhancedEventBatcher } from './EnhancedEventBatcher';
import { BehaviorTracker } from './BehaviorTracker';
import { TrustTracker } from './TrustTracker';
import { UIPerformanceTracker } from './UIPerformanceTracker';
import { ContentIntelligenceTracker } from './ContentIntelligenceTracker';
import { LearningAnalyticsTracker } from './LearningAnalyticsTracker';
import { ChatAnalyticsTracker } from './ChatAnalyticsTracker';

const logger = createLogger('ComprehensiveAnalyticsManager');

interface TrackerStatus {
  enabled: boolean;
  initialized: boolean;
  errorCount: number;
  lastError?: string;
  lastActivity: number;
}

export class ComprehensiveAnalyticsManager {
  private eventBatcher: EnhancedEventBatcher;
  private trackers: {
    behavior?: BehaviorTracker;
    trust?: TrustTracker;
    uiPerformance?: UIPerformanceTracker;
    contentIntelligence?: ContentIntelligenceTracker;
    learningAnalytics?: LearningAnalyticsTracker;
    chatAnalytics?: ChatAnalyticsTracker;
  } = {};

  private trackerStatus: Map<string, TrackerStatus> = new Map();
  private userId: string;
  private sessionId: string;
  private isInitialized = false;
  
  private readonly config: EnhancedMetricsConfig = {
    batchSize: 75,
    flushInterval: 45000,
    enableDebugLogging: process.env.NODE_ENV === 'development',
    privacyMode: 'full',
    enableMouseTracking: true,
    enableContentAnalysis: true,
    enableTrustTracking: true,
    enablePerformanceTracking: true,
    samplingRates: {
      scroll: 0.3,
      mouse: 0.2,
      performance: 0.8
    }
  };

  constructor(userId: string, sessionId: string) {
    this.userId = userId;
    this.sessionId = sessionId;
    
    // Initialize event batcher first
    this.eventBatcher = new EnhancedEventBatcher();
    
    this.initializeTrackers();
  }

  private initializeTrackers(): void {
    try {
      // Initialize all trackers with error handling
      this.initializeTracker('behavior', () => 
        new BehaviorTracker(this.config, this.handleEvent.bind(this))
      );

      this.initializeTracker('trust', () => 
        new TrustTracker(this.userId, this.sessionId, this.config, this.handleEvent.bind(this))
      );

      this.initializeTracker('uiPerformance', () => 
        new UIPerformanceTracker(this.config, this.handleEvent.bind(this))
      );

      this.initializeTracker('contentIntelligence', () => 
        new ContentIntelligenceTracker(this.config, this.handleEvent.bind(this))
      );

      this.initializeTracker('learningAnalytics', () => 
        new LearningAnalyticsTracker(this.userId, this.sessionId, this.config, this.handleEvent.bind(this))
      );

      this.initializeTracker('chatAnalytics', () => 
        new ChatAnalyticsTracker(this.config, this.handleEvent.bind(this))
      );

      this.setupGlobalErrorHandling();
      this.setupPeriodicHealthCheck();
      this.setupCleanupHandlers();

      this.isInitialized = true;
      logger.log('All analytics trackers initialized successfully');

      // Track initialization success
      this.handleEvent({
        event_type: 'analytics_system_initialized',
        event_category: 'performance',
        event_priority: 'high',
        event_data: {
          tracker_count: Object.keys(this.trackers).length,
          successful_trackers: Array.from(this.trackerStatus.entries())
            .filter(([, status]) => status.initialized)
            .map(([name]) => name),
          initialization_time_ms: Date.now(),
          config: {
            mouse_tracking: this.config.enableMouseTracking,
            content_analysis: this.config.enableContentAnalysis,
            trust_tracking: this.config.enableTrustTracking,
            performance_tracking: this.config.enablePerformanceTracking
          }
        },
        client_timestamp: new Date().toISOString()
      });

    } catch (error) {
      logger.error('Failed to initialize analytics trackers:', error);
      
      this.handleEvent({
        event_type: 'analytics_initialization_error',
        event_category: 'performance',
        event_priority: 'critical',
        event_data: {
          error_message: error instanceof Error ? error.message : String(error),
          error_stack: error instanceof Error ? error.stack?.slice(0, 1000) : undefined
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private initializeTracker<T>(
    name: string, 
    factory: () => T,
    required: boolean = false
  ): void {
    try {
      const tracker = factory();
      (this.trackers as any)[name] = tracker;
      
      this.trackerStatus.set(name, {
        enabled: true,
        initialized: true,
        errorCount: 0,
        lastActivity: Date.now()
      });

      logger.log(`${name} tracker initialized successfully`);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      this.trackerStatus.set(name, {
        enabled: false,
        initialized: false,
        errorCount: 1,
        lastError: errorMessage,
        lastActivity: Date.now()
      });

      logger.error(`Failed to initialize ${name} tracker:`, error);

      if (required) {
        throw error;
      }
    }
  }

  private handleEvent(event: UnifiedAnalyticsEvent): void {
    try {
      // Enrich event with system metadata
      const enrichedEvent: UnifiedAnalyticsEvent = {
        ...event,
        user_id: event.user_id || this.userId,
        session_id: event.session_id || this.sessionId,
        event_priority: event.event_priority || this.determinePriority(event),
        event_data: {
          ...event.event_data,
          system_metadata: {
            user_agent: navigator.userAgent,
            viewport: {
              width: window.innerWidth,
              height: window.innerHeight
            },
            url: window.location.href,
            timestamp: Date.now()
          }
        }
      };

      // Send to event batcher
      this.eventBatcher.addEvent(enrichedEvent);

      // Also send to Mixpanel for real-time dashboards
      try {
        analytics.track(enrichedEvent.event_type, {
          category: enrichedEvent.event_category,
          priority: enrichedEvent.event_priority,
          ...enrichedEvent.event_data
        });
      } catch (mixpanelError) {
        // Non-critical error, log and continue
        logger.warn('Failed to send event to Mixpanel:', mixpanelError);
      }

      // Update tracker activity
      const trackerName = this.inferTrackerFromEvent(enrichedEvent);
      if (trackerName) {
        const status = this.trackerStatus.get(trackerName);
        if (status) {
          status.lastActivity = Date.now();
        }
      }

    } catch (error) {
      logger.error('Error handling analytics event:', error);
      this.incrementTrackerError('eventHandler');
    }
  }

  private determinePriority(event: UnifiedAnalyticsEvent): EventPriority {
    // Critical: errors, failures, security issues
    if (event.event_type.includes('error') || 
        event.event_type.includes('failure') ||
        event.event_type.includes('anomaly') ||
        event.event_category === 'trust' && event.event_data.confidence_level === 'critical') {
      return 'critical';
    }

    // High: user interactions, detection results, chat events, trust changes
    if (event.event_category === 'chat' ||
        event.event_type.includes('interaction') ||
        event.event_type.includes('detection') ||
        event.event_type.includes('trust_score') ||
        event.event_type === 'post_view') {
      return 'high';
    }

    // Medium: UI events, content analysis, learning progress
    if (event.event_category === 'ui' ||
        event.event_category === 'content' ||
        event.event_category === 'learning' ||
        event.event_category === 'behavior') {
      return 'medium';
    }

    // Low: background metrics, performance monitoring
    return 'low';
  }

  private inferTrackerFromEvent(event: UnifiedAnalyticsEvent): string | null {
    if (event.event_category === 'behavior') return 'behavior';
    if (event.event_category === 'trust') return 'trust';
    if (event.event_category === 'ui') return 'uiPerformance';
    if (event.event_category === 'content') return 'contentIntelligence';
    if (event.event_category === 'learning') return 'learningAnalytics';
    if (event.event_category === 'chat') return 'chatAnalytics';
    return null;
  }

  private setupGlobalErrorHandling(): void {
    // Catch and track any unhandled errors from trackers
    window.addEventListener('error', (event) => {
      if (event.error?.stack?.includes('BehaviorTracker') ||
          event.error?.stack?.includes('TrustTracker') ||
          event.error?.stack?.includes('UIPerformanceTracker') ||
          event.error?.stack?.includes('ContentIntelligenceTracker') ||
          event.error?.stack?.includes('LearningAnalyticsTracker') ||
          event.error?.stack?.includes('ChatAnalyticsTracker')) {
        
        this.handleEvent({
          event_type: 'tracker_runtime_error',
          event_category: 'performance',
          event_priority: 'critical',
          event_data: {
            error_message: event.error.message,
            error_stack: event.error.stack?.slice(0, 1000),
            error_source: event.filename,
            error_line: event.lineno,
            tracker_health: this.getTrackerHealthSummary()
          },
          client_timestamp: new Date().toISOString()
        });
      }
    });
  }

  private setupPeriodicHealthCheck(): void {
    // Check tracker health every 2 minutes
    setInterval(() => {
      this.performHealthCheck();
    }, 120000);
  }

  private setupCleanupHandlers(): void {
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      this.destroy();
    });

    // Cleanup on visibility change (after timeout)
    let hideTimer: number | null = null;
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        hideTimer = window.setTimeout(() => {
          this.destroy();
        }, getSessionHiddenTimeoutMs());
      } else if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
      }
    });
  }

  private performHealthCheck(): void {
    const healthData = this.getTrackerHealthSummary();
    
    this.handleEvent({
      event_type: 'analytics_health_check',
      event_category: 'performance',
      event_priority: 'low',
      event_data: {
        ...healthData,
        event_queue_stats: this.eventBatcher.getQueueStats(),
        memory_usage: this.getMemoryUsageStats(),
        performance_metrics: this.getPerformanceMetrics()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private getTrackerHealthSummary(): Record<string, any> {
    const summary: Record<string, any> = {};
    
    this.trackerStatus.forEach((status, name) => {
      summary[name] = {
        enabled: status.enabled,
        initialized: status.initialized,
        error_count: status.errorCount,
        last_error: status.lastError,
        time_since_activity_ms: Date.now() - status.lastActivity
      };
    });

    return summary;
  }

  private getMemoryUsageStats(): Record<string, number> | null {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      return {
        used_js_heap_size_mb: Math.round(memory.usedJSHeapSize / 1024 / 1024),
        total_js_heap_size_mb: Math.round(memory.totalJSHeapSize / 1024 / 1024),
        js_heap_size_limit_mb: Math.round(memory.jsHeapSizeLimit / 1024 / 1024)
      };
    }
    return null;
  }

  private getPerformanceMetrics(): Record<string, number> {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    
    return {
      dom_content_loaded_ms: navigation?.domContentLoadedEventEnd - navigation?.domContentLoadedEventStart || 0,
      load_complete_ms: navigation?.loadEventEnd - navigation?.loadEventStart || 0,
      page_load_time_ms: navigation?.loadEventEnd - navigation?.fetchStart || 0
    };
  }

  private incrementTrackerError(trackerName: string): void {
    const status = this.trackerStatus.get(trackerName);
    if (status) {
      status.errorCount++;
      status.lastActivity = Date.now();
    }
  }

  // Public API methods
  public trackPostView(postId: string, postElement: Element): void {
    try {
      // BehaviorTracker automatically observes posts via MutationObserver
      this.trackers.uiPerformance?.trackIconRenderPerformance(postId, postElement);
      // ContentIntelligenceTracker automatically tracks via MutationObserver
      
      // Track with learning analytics
      if (this.trackers.learningAnalytics) {
        (this.trackers.learningAnalytics as any).trackInteractionAccuracy?.(true, 0.8);
      }
    } catch (error) {
      logger.error('Error tracking post view:', error);
      this.incrementTrackerError('postView');
    }
  }

  public trackDetectionResult(
    postId: string, 
    result: 'ai' | 'human' | 'uncertain', 
    confidence: number,
    metadata: Record<string, unknown> = {}
  ): void {
    try {
      this.trackers.trust?.trackDetectionResult(postId, result, confidence, metadata);
      this.trackers.trust?.trackComparativeBehavior(postId, result === 'ai');
    } catch (error) {
      logger.error('Error tracking detection result:', error);
      this.incrementTrackerError('detectionResult');
    }
  }

  public trackUserFeedback(
    postId: string, 
    feedback: 'correct' | 'incorrect' | 'uncertain'
  ): void {
    try {
      this.trackers.trust?.trackUserFeedback(postId, feedback);
      
      if (this.trackers.learningAnalytics) {
        (this.trackers.learningAnalytics as any).trackInteractionAccuracy?.(
          feedback === 'correct', 
          feedback === 'correct' ? 0.9 : 0.3
        );
      }
    } catch (error) {
      logger.error('Error tracking user feedback:', error);
      this.incrementTrackerError('userFeedback');
    }
  }

  public trackChatStart(postId: string): void {
    try {
      const sessionId = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      this.trackers.chatAnalytics?.startConversation(sessionId, postId);
      // TrustTracker doesn't have trackChatStart method - handled by chat analytics
    } catch (error) {
      logger.error('Error tracking chat start:', error);
      this.incrementTrackerError('chatStart');
    }
  }

  public trackChatMessage(
    sessionId: string, 
    message: string, 
    isUser: boolean, 
    responseTime?: number
  ): void {
    try {
      if (isUser) {
        this.trackers.chatAnalytics?.trackUserMessage(sessionId, message);
      } else if (responseTime !== undefined) {
        this.trackers.chatAnalytics?.trackAssistantMessage(sessionId, message, responseTime);
      }
    } catch (error) {
      logger.error('Error tracking chat message:', error);
      this.incrementTrackerError('chatMessage');
    }
  }

  public trackUIError(errorType: string, errorMessage: string, context: any): void {
    try {
      this.trackers.uiPerformance?.trackErrorRecovery(errorType, 'user_retry', false);
    } catch (error) {
      logger.error('Error tracking UI error:', error);
      this.incrementTrackerError('uiError');
    }
  }

  public trackPerformanceMetric(endpoint: string, responseTime: number, statusCode: number): void {
    try {
      this.handleEvent({
        event_type: 'api_response_time',
        event_category: 'performance',
        event_priority: statusCode >= 400 ? 'high' : 'medium',
        event_data: {
          endpoint,
          response_time_ms: responseTime,
          status_code: statusCode,
          performance_grade: responseTime < 1000 ? 'good' : responseTime < 3000 ? 'fair' : 'poor'
        },
        client_timestamp: new Date().toISOString()
      });
    } catch (error) {
      logger.error('Error tracking performance metric:', error);
      this.incrementTrackerError('performanceMetric');
    }
  }

  public getSystemHealth(): Record<string, any> {
    return {
      initialized: this.isInitialized,
      trackers: this.getTrackerHealthSummary(),
      event_queue: this.eventBatcher.getQueueStats(),
      memory: this.getMemoryUsageStats(),
      session: {
        user_id: this.userId,
        session_id: this.sessionId,
        uptime_ms: Date.now() - (this.trackerStatus.get('behavior')?.lastActivity || Date.now())
      }
    };
  }

  public async flushEvents(): Promise<void> {
    try {
      await this.eventBatcher.flushAll();
    } catch (error) {
      logger.error('Error flushing events:', error);
    }
  }

  public destroy(): void {
    try {
      logger.log('Destroying comprehensive analytics manager');

      // Destroy all trackers
      Object.entries(this.trackers).forEach(([name, tracker]) => {
        try {
          if (tracker && typeof (tracker as any).destroy === 'function') {
            (tracker as any).destroy();
          }
        } catch (error) {
          logger.warn(`Error destroying ${name} tracker:`, error);
        }
      });

      // Flush final events
      this.eventBatcher.flushAll().catch(error => {
        logger.warn('Error in final event flush:', error);
      });

      // Destroy event batcher
      this.eventBatcher.destroy();

      // Clear references
      this.trackers = {};
      this.trackerStatus.clear();
      this.isInitialized = false;

    } catch (error) {
      logger.error('Error during analytics manager destruction:', error);
    }
  }
}