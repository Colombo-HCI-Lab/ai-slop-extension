# AI Slop Extension Metrics Collection Plan - V2

## Executive Summary

This document outlines a comprehensive plan to implement user behavior analytics for the AI Slop Detection browser extension. The system will collect detailed metrics on user interactions, post consumption patterns, and chat engagement to enable data-driven product improvements and user experience optimization while maintaining strict privacy standards and minimal performance impact.

## Table of Contents
1. [Current State Analysis](#current-state-analysis)
2. [Proposed Database Schema](#proposed-database-schema)
3. [Migration Strategy](#migration-strategy)
4. [Browser Extension Architecture](#browser-extension-architecture)
5. [API Design](#api-design)
6. [Data Collection Implementation](#data-collection-implementation)
7. [Error Handling & Edge Cases](#error-handling--edge-cases)
8. [Testing Strategy](#testing-strategy)
9. [Privacy & Compliance](#privacy--compliance)
10. [Implementation Timeline](#implementation-timeline)
11. [Performance Considerations](#performance-considerations)
12. [Success Metrics & KPIs](#success-metrics--kpis)

## Current State Analysis

### Existing Database Schema

The current system has a basic foundation with:

- **Post Table**: Stores Facebook posts with AI detection results (`post_id`, `content`, `verdict`, `confidence`, detection probabilities)
- **UserSession Table**: Basic user tracking with UUID-based identification
- **Chat Table**: Individual chat messages linked to posts and user sessions with composite indexes
- **PostMedia Table**: Media files with deduplication fields (`content_hash`, `normalized_url`)

### Gap Analysis

**Missing Critical Components:**
- User behavioral metrics (scroll speed, reading time, interaction patterns)
- Post interaction analytics (time to interaction, icon visibility duration)
- Session-level metrics aggregation
- Chat session tracking and duration metrics
- Generic event tracking for detailed analytics
- User-post relationship tracking
- Detection accuracy feedback mechanism
- A/B testing framework support

## Proposed Database Schema

### Migration Strategy

All schema changes will be implemented through Alembic migrations with proper rollback capabilities:

```python
# backend/db/migrations/versions/003_add_metrics_tables.py
"""Add comprehensive metrics tracking tables

Revision ID: 003_add_metrics_tables
Revises: 002_add_content_dedup_fields
Create Date: 2025-08-27
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create user table with behavioral metrics
    op.create_table('user',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('extension_user_id', sa.String(255), unique=True, nullable=False),
        sa.Column('avg_scroll_speed', sa.Float()),
        sa.Column('avg_posts_per_minute', sa.Float()),
        sa.Column('total_posts_viewed', sa.Integer(), default=0),
        sa.Column('total_interactions', sa.Integer(), default=0),
        sa.Column('browser_info', sa.JSON()),
        sa.Column('timezone', sa.String(50)),
        sa.Column('locale', sa.String(10)),
        sa.Column('experiment_groups', sa.JSON()),  # For A/B testing
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_user_extension_user_id', 'user', ['extension_user_id'])
    op.create_index('ix_user_last_active', 'user', ['last_active_at'])
    
    # Enhanced post table modifications
    op.add_column('post', sa.Column('content_length', sa.Integer()))
    op.add_column('post', sa.Column('post_type', sa.String(50)))
    op.add_column('post', sa.Column('has_media', sa.Boolean(), default=False))
    op.add_column('post', sa.Column('facebook_url', sa.Text()))
    op.add_column('post', sa.Column('content_hash', sa.String(64)))
    op.add_column('post', sa.Column('detected_at', sa.DateTime(timezone=True)))
    op.add_column('post', sa.Column('group_id', sa.String(255)))
    op.add_column('post', sa.Column('group_name', sa.String(255)))
    op.create_index('ix_post_content_hash', 'post', ['content_hash'])
    op.create_index('ix_post_detected_at', 'post', ['detected_at'])
    op.create_index('ix_post_group_id', 'post', ['group_id'])
    
    # User post analytics table
    op.create_table('user_post_analytics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('post_id', sa.String(255), sa.ForeignKey('post.post_id', ondelete='CASCADE'), nullable=False),
        sa.Column('interaction_type', sa.String(20), default='viewed'),
        sa.Column('backend_response_time_ms', sa.Integer()),
        sa.Column('time_to_interaction_ms', sa.Integer()),
        sa.Column('icon_visibility_duration_ms', sa.Integer()),
        sa.Column('reading_time_ms', sa.Integer()),
        sa.Column('scroll_depth_percentage', sa.Float()),
        sa.Column('viewport_time_ms', sa.Integer()),
        sa.Column('chat_session_count', sa.Integer(), default=0),
        sa.Column('total_chat_duration_ms', sa.Integer(), default=0),
        sa.Column('total_messages_sent', sa.Integer(), default=0),
        sa.Column('suggested_questions_used', sa.Integer(), default=0),
        sa.Column('accuracy_feedback', sa.String(20)),  # 'correct', 'incorrect', 'unsure'
        sa.Column('times_viewed', sa.Integer(), default=1),
        sa.Column('first_viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('interaction_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('user_id', 'post_id', name='uq_user_post')
    )
    op.create_index('ix_user_post_analytics_user_id', 'user_post_analytics', ['user_id'])
    op.create_index('ix_user_post_analytics_post_id', 'user_post_analytics', ['post_id'])
    op.create_index('ix_user_post_analytics_interaction', 'user_post_analytics', ['interaction_type'])
    op.create_index('ix_user_post_analytics_viewed_at', 'user_post_analytics', ['first_viewed_at'])
    
    # Enhanced user session table
    op.create_table('user_session_enhanced',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_token', sa.String(255), unique=True),
        sa.Column('ip_hash', sa.String(64)),  # Hashed IP for geographic analytics
        sa.Column('user_agent', sa.Text()),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('posts_viewed', sa.Integer(), default=0),
        sa.Column('posts_analyzed', sa.Integer(), default=0),
        sa.Column('posts_interacted', sa.Integer(), default=0),
        sa.Column('avg_scroll_speed', sa.Float()),
        sa.Column('avg_posts_per_minute', sa.Float()),
        sa.Column('total_scroll_distance', sa.Integer()),
        sa.Column('active_time_seconds', sa.Integer()),
        sa.Column('idle_time_seconds', sa.Integer()),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('end_reason', sa.String(50)),  # 'user_logout', 'timeout', 'browser_close'
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_user_session_enhanced_user_id', 'user_session_enhanced', ['user_id'])
    op.create_index('ix_user_session_enhanced_started_at', 'user_session_enhanced', ['started_at'])
    op.create_index('ix_user_session_enhanced_token', 'user_session_enhanced', ['session_token'])
    
    # Chat session table
    op.create_table('chat_session',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_post_analytics_id', sa.String(36), sa.ForeignKey('user_post_analytics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_token', sa.String(255), unique=True),
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('message_count', sa.Integer(), default=0),
        sa.Column('user_message_count', sa.Integer(), default=0),
        sa.Column('assistant_message_count', sa.Integer(), default=0),
        sa.Column('suggested_question_clicks', sa.Integer(), default=0),
        sa.Column('average_response_time_ms', sa.Integer()),
        sa.Column('max_response_time_ms', sa.Integer()),
        sa.Column('ended_by', sa.String(20), default='close'),
        sa.Column('satisfaction_rating', sa.Integer()),  # 1-5 scale
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_chat_session_analytics_id', 'chat_session', ['user_post_analytics_id'])
    op.create_index('ix_chat_session_started_at', 'chat_session', ['started_at'])
    
    # Analytics event table for granular tracking
    op.create_table('analytics_event',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE')),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('user_session_enhanced.id', ondelete='CASCADE')),
        sa.Column('post_id', sa.String(255), sa.ForeignKey('post.post_id', ondelete='CASCADE')),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_category', sa.String(50)),  # 'interaction', 'performance', 'error'
        sa.Column('event_value', sa.Float()),
        sa.Column('event_label', sa.String(255)),
        sa.Column('metadata', sa.JSON()),
        sa.Column('client_timestamp', sa.DateTime(timezone=True)),
        sa.Column('server_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_analytics_event_user_type', 'analytics_event', ['user_id', 'event_type'])
    op.create_index('ix_analytics_event_created', 'analytics_event', ['created_at'])
    op.create_index('ix_analytics_event_post', 'analytics_event', ['post_id'])
    op.create_index('ix_analytics_event_session', 'analytics_event', ['session_id'])
    op.create_index('ix_analytics_event_category', 'analytics_event', ['event_category'])
    
    # Performance metrics table for system monitoring
    op.create_table('performance_metric',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(50)),
        sa.Column('endpoint', sa.String(255)),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_performance_metric_name_time', 'performance_metric', ['metric_name', 'timestamp'])

def downgrade():
    op.drop_table('performance_metric')
    op.drop_table('analytics_event')
    op.drop_table('chat_session')
    op.drop_table('user_session_enhanced')
    op.drop_table('user_post_analytics')
    op.drop_column('post', 'group_name')
    op.drop_column('post', 'group_id')
    op.drop_column('post', 'detected_at')
    op.drop_column('post', 'content_hash')
    op.drop_column('post', 'facebook_url')
    op.drop_column('post', 'has_media')
    op.drop_column('post', 'post_type')
    op.drop_column('post', 'content_length')
    op.drop_table('user')
```

## Browser Extension Architecture (current)

Extension structure and integration points:
- Background split: 
- Content split: 
- Shared utilities: 
- Logging: all logs gated by  via  and DefinePlugin

The metrics layer should integrate with this architecture:
- Add a metrics client under  and send batches via background by adding a new message type in  and a handler in .
- Reuse  via background API for robust sending.

### 1. Core Metrics Collection Service (aligned to new extension structure)

```typescript
// browser-extension/src/content/metrics/MetricsCollector.ts
// Note: Uses shared/logger (scoped), shared/net/retry via background, and shared/messages
import { debounce, throttle } from '../utils/performance';

interface MetricsConfig {
  batchSize: number;
  flushInterval: number;
  enableDebugLogging: boolean;
  privacyMode: 'strict' | 'balanced' | 'full';
}

export class MetricsCollector {
  private userId: string;
  private sessionId: string;
  private eventBuffer: AnalyticsEvent[] = [];
  private postVisibilityObserver: IntersectionObserver;
  private scrollMetrics: ScrollMetrics;
  private performanceObserver: PerformanceObserver;
  private config: MetricsConfig;
  
  constructor(config: MetricsConfig) {
    this.config = config;
    this.initializeObservers();
    this.startAutoFlush();
  }
  
  // Initialize intersection observer for post visibility
  private initializeObservers(): void {
    this.postVisibilityObserver = new IntersectionObserver(
      this.handlePostVisibility.bind(this),
      {
        threshold: [0, 0.25, 0.5, 0.75, 1.0],
        rootMargin: '50px'
      }
    );
    
    // Performance observer for API timings (uses Performance API)
    this.performanceObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'measure' && entry.name.startsWith('api-')) {
          this.trackPerformance(entry.name, entry.duration);
        }
      }
    });
    this.performanceObserver.observe({ entryTypes: ['measure'] });
  }
  
  // Track post visibility with viewport time
  private handlePostVisibility(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      const postId = entry.target.getAttribute('data-post-id');
      if (!postId) return;
      
      if (entry.isIntersecting) {
        this.startPostViewTracking(postId, entry.intersectionRatio);
      } else {
        this.endPostViewTracking(postId);
      }
    });
  }
  
  // Debounced scroll tracking
  public trackScrollBehavior = debounce((scrollData: ScrollData): void => {
    this.scrollMetrics.update(scrollData);
    
    if (this.scrollMetrics.shouldReport()) {
      this.addEvent({
        type: 'scroll_behavior',
        category: 'interaction',
        value: this.scrollMetrics.getAverageSpeed(),
        metadata: {
          totalDistance: this.scrollMetrics.totalDistance,
          pauseCount: this.scrollMetrics.pauseCount,
          direction: this.scrollMetrics.primaryDirection
        }
      });
    }
  }, 500);
  
  // Batch event sending with retry logic
  public async flushEvents(): Promise<void> {
    if (this.eventBuffer.length === 0) return;
    
    const events = [...this.eventBuffer];
    this.eventBuffer = [];
    
    try {
      // In the current architecture, send via background script to reuse
      // fetchJsonWithRetry and API base handling. Define a new message type
      // in src/shared/messages.ts (e.g., METRICS_BATCH) and handle it in
      // src/background/messaging.ts by calling a lightweight metrics endpoint.
      await this.sendWithBackground(events);
    } catch (error) {
      // Use shared logger; disabled in production builds
      logger.error('Failed to send metrics after retries:', error);
      // Re-add failed events to buffer with exponential backoff
      this.eventBuffer.unshift(...events.slice(0, this.config.batchSize));
    }
  }
  
  private async sendWithBackground(events: AnalyticsEvent[]): Promise<void> {
    await sendMetricsBatch({ sessionId: this.sessionId, events });
  }

  // (Optional) Direct retry path if calling backend from content, but we prefer background
  private async sendWithRetry(events: AnalyticsEvent[], retries = 3): Promise<void> {
    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const response = await fetch('/api/v1/analytics/events', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: this.sessionId,
            events: this.sanitizeEvents(events)
          })
        });
        
        if (response.ok) return;
        
        if (response.status === 429) {
          // Rate limited - wait exponentially
          await this.wait(Math.pow(2, attempt) * 1000);
        } else if (response.status >= 500) {
          // Server error - retry with backoff
          await this.wait(Math.pow(2, attempt) * 500);
        } else {
          // Client error - don't retry
          throw new Error(`Client error: ${response.status}`);
        }
      } catch (error) {
        if (attempt === retries - 1) throw error;
        await this.wait(Math.pow(2, attempt) * 1000);
      }
    }
  }
  
  // Privacy-aware event sanitization
  private sanitizeEvents(events: AnalyticsEvent[]): AnalyticsEvent[] {
    return events.map(event => {
      if (this.config.privacyMode === 'strict') {
        // Remove potentially identifying information
        delete event.metadata?.userAgent;
        delete event.metadata?.screenResolution;
        delete event.metadata?.language;
      }
      return event;
    });
  }
  
  // Cleanup on extension unload
  public destroy(): void {
    this.postVisibilityObserver.disconnect();
    this.performanceObserver.disconnect();
    this.flushEvents(); // Final flush
  }
}
```

### 2. Enhanced Post Observer (hooks in src/content/observer.ts)

```typescript
// browser-extension/src/content/observer.ts
export class FacebookPostObserver {
  private metricsCollector: MetricsCollector;
  private postTracker: Map<string, PostTrackingData> = new Map();
  private iconInteractionHandler: IconInteractionHandler;
  
  constructor(metricsCollector: MetricsCollector) {
    this.metricsCollector = metricsCollector;
    this.iconInteractionHandler = new IconInteractionHandler(metricsCollector);
    this.initializeTracking();
  }
  
  private initializeTracking(): void {
    // Track post processing (leverages existing MutationObserver)
    this.observer = new MutationObserver(this.handleMutations.bind(this));
    
    // Track user interactions
    document.addEventListener('click', this.handleClick.bind(this), true);
    document.addEventListener('scroll', this.handleScroll.bind(this), { passive: true });
    
    // Track page visibility changes
    document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
    
    // Track performance metrics using performance.mark/measure around background calls
    this.trackPerformanceMetrics();
  }
  
  private processPost(postElement: Element): void {
    const postId = this.extractPostId(postElement);
    if (!postId || this.postTracker.has(postId)) return;
    
    const startTime = performance.now();
    
    // Extract post data
    const postData = this.extractPostData(postElement);
    
    // Track post view
    this.postTracker.set(postId, {
      firstSeen: Date.now(),
      element: postElement,
      hasIcon: false,
      interacted: false
    });
    
    // Send for AI detection (currently delegated to background via content/messaging)
    this.requestAIDetection(postId, postData).then(result => {
      const processingTime = performance.now() - startTime;
      
      // Track detection performance
      this.metricsCollector.trackEvent({
        type: 'post_processed',
        category: 'performance',
        value: processingTime,
        metadata: {
          postId,
          verdict: result.verdict,
          confidence: result.confidence,
          hasMedia: postData.hasMedia,
          contentLength: postData.content.length
        }
      });
      
      // Inject icon if AI detected
      if (result.isAiSlop) {
        this.injectIcon(postElement, postId, result);
      }
    }).catch(error => {
      // Track error
      this.metricsCollector.trackEvent({
        type: 'detection_error',
        category: 'error',
        metadata: {
          postId,
          error: error.message,
          errorType: error.name
        }
      });
    });
  }
  
  private trackReadingTime(postElement: Element): void {
    const postId = postElement.getAttribute('data-post-id');
    const postHeight = postElement.getBoundingClientRect().height;
    const wordsCount = this.estimateWordCount(postElement);
    
    // Use intersection observer to track actual viewport time
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const visiblePercentage = entry.intersectionRatio;
          const estimatedReadingTime = this.calculateReadingTime(wordsCount, visiblePercentage);
          
          this.metricsCollector.trackEvent({
            type: 'post_reading',
            category: 'interaction',
            value: estimatedReadingTime,
            metadata: {
              postId,
              wordsCount,
              visiblePercentage,
              postHeight
            }
          });
        }
      });
    }, { threshold: [0.25, 0.5, 0.75, 1.0] });
    
    observer.observe(postElement);
  }
  
  private handleIconInteraction(iconElement: Element, interactionType: string): void {
    const postId = iconElement.getAttribute('data-post-id');
    const trackingData = this.postTracker.get(postId);
    
    if (!trackingData) return;
    
    const timeToInteraction = Date.now() - trackingData.firstSeen;
    
    this.metricsCollector.trackEvent({
      type: `icon_${interactionType}`,
      category: 'interaction',
      value: timeToInteraction,
      metadata: {
        postId,
        previousInteraction: trackingData.lastInteraction,
        iconVisibleDuration: trackingData.iconVisibleDuration
      }
    });
    
    trackingData.lastInteraction = interactionType;
    trackingData.interacted = true;
  }
}
```

### 3. Chat Metrics Tracking

```typescript
// browser-extension/src/content/metrics/ChatMetricsTracker.ts
export class ChatMetricsTracker {
  private currentSession: ChatSession | null = null;
  private messageTimings: Map<string, number> = new Map();
  private typingStartTime: number | null = null;
  
  startChatSession(postId: string, userId: string): string {
    const sessionId = generateSessionId();
    
    this.currentSession = {
      id: sessionId,
      postId,
      userId,
      startTime: Date.now(),
      messageCount: 0,
      suggestedQuestionsUsed: 0
    };
    
    this.trackEvent({
      type: 'chat_session_start',
      category: 'chat',
      metadata: { sessionId, postId }
    });
    
    return sessionId;
  }
  
  trackMessageSent(message: string, isSuggestedQuestion: boolean = false): void {
    if (!this.currentSession) return;
    
    const typingDuration = this.typingStartTime 
      ? Date.now() - this.typingStartTime 
      : null;
    
    this.currentSession.messageCount++;
    if (isSuggestedQuestion) {
      this.currentSession.suggestedQuestionsUsed++;
    }
    
    this.trackEvent({
      type: 'chat_message_sent',
      category: 'chat',
      value: message.length,
      metadata: {
        sessionId: this.currentSession.id,
        typingDuration,
        isSuggestedQuestion,
        messageNumber: this.currentSession.messageCount
      }
    });
    
    this.typingStartTime = null;
  }
  
  trackTypingStart(): void {
    if (!this.typingStartTime) {
      this.typingStartTime = Date.now();
    }
  }
  
  endChatSession(endReason: 'close' | 'minimize' | 'navigate_away'): void {
    if (!this.currentSession) return;
    
    const duration = Date.now() - this.currentSession.startTime;
    
    this.trackEvent({
      type: 'chat_session_end',
      category: 'chat',
      value: duration,
      metadata: {
        sessionId: this.currentSession.id,
        endReason,
        messageCount: this.currentSession.messageCount,
        suggestedQuestionsUsed: this.currentSession.suggestedQuestionsUsed,
        averageResponseTime: this.calculateAverageResponseTime()
      }
    });
    
    this.currentSession = null;
    this.messageTimings.clear();
  }
}
```

## API Design

### Enhanced API Endpoints with Validation

```python
# backend/api/v1/endpoints/analytics.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio

from schemas.analytics import (
    UserInitRequest, UserInitResponse,
    SessionStartRequest, SessionEndRequest,
    EventBatchRequest, AnalyticsEvent,
    PostInteractionRequest, ChatSessionMetrics
)
from services.analytics_service import AnalyticsService
from services.rate_limiter import RateLimiter
from core.dependencies import get_db, get_current_user

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.post("/users/initialize", response_model=UserInitResponse)
async def initialize_user(
    request: UserInitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends()
):
    """Initialize or update user profile with metrics."""
    try:
        # Rate limiting per IP
        await rate_limiter.check_rate_limit(request.client_ip, limit=10, window=60)
        
        service = AnalyticsService(db)
        user = await service.initialize_user(
            extension_user_id=request.extension_user_id,
            browser_info=request.browser_info,
            timezone=request.timezone,
            locale=request.locale
        )
        
        # Start new session
        session = await service.start_session(user.id, request.browser_info)
        
        # Background task for geolocation (non-blocking)
        background_tasks.add_task(
            service.enrich_user_data,
            user.id,
            request.client_ip
        )
        
        return UserInitResponse(
            user_id=user.id,
            session_id=session.id,
            experiment_groups=user.experiment_groups or []
        )
        
    except Exception as e:
        logger.error(f"User initialization failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize user")

@router.post("/events/batch")
async def submit_event_batch(
    request: EventBatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Submit batch of analytics events."""
    try:
        # Validate event batch size
        if len(request.events) > 1000:
            raise HTTPException(status_code=400, detail="Batch size exceeds limit (1000)")
        
        # Validate timestamps (prevent future events)
        current_time = datetime.utcnow()
        for event in request.events:
            if event.client_timestamp > current_time:
                raise HTTPException(status_code=400, detail="Invalid future timestamp")
            
            # Check if event is too old (>7 days)
            if current_time - event.client_timestamp > timedelta(days=7):
                continue  # Skip old events silently
        
        service = AnalyticsService(db)
        
        # Process events asynchronously
        background_tasks.add_task(
            service.process_event_batch,
            session_id=request.session_id,
            events=request.events,
            user_id=current_user
        )
        
        return {"status": "accepted", "count": len(request.events)}
        
    except Exception as e:
        logger.error(f"Event batch processing failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process events")

@router.post("/posts/{post_id}/interactions")
async def track_post_interaction(
    post_id: str,
    request: PostInteractionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Track user interaction with a post."""
    try:
        service = AnalyticsService(db)
        
        # Validate interaction type
        valid_types = ['viewed', 'clicked', 'ignored', 'chatted', 'feedback_positive', 'feedback_negative']
        if request.interaction_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid interaction type: {request.interaction_type}")
        
        analytics = await service.track_post_interaction(
            user_id=request.user_id,
            post_id=post_id,
            interaction_type=request.interaction_type,
            metrics={
                'backend_response_time_ms': request.backend_response_time_ms,
                'time_to_interaction_ms': request.time_to_interaction_ms,
                'reading_time_ms': request.reading_time_ms,
                'scroll_depth_percentage': request.scroll_depth_percentage,
                'viewport_time_ms': request.viewport_time_ms
            }
        )
        
        return {"status": "tracked", "analytics_id": analytics.id}
        
    except Exception as e:
        logger.error(f"Post interaction tracking failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to track interaction")

@router.get("/dashboard/{user_id}")
async def get_user_dashboard(
    user_id: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get user analytics dashboard data."""
    try:
        service = AnalyticsService(db)
        
        # Default to last 30 days
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        dashboard_data = await service.get_user_dashboard(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Dashboard retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard")
```

### Analytics Service Implementation

```python
# backend/services/analytics_service.py
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
import asyncio
import hashlib

from models import User, UserPostAnalytics, AnalyticsEvent, UserSessionEnhanced
from schemas.analytics import AnalyticsEvent as EventSchema
from utils.caching import cache_result

class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def initialize_user(
        self,
        extension_user_id: str,
        browser_info: Dict[str, Any],
        timezone: str,
        locale: str
    ) -> User:
        """Initialize or update user with deduplication."""
        # Check for existing user
        stmt = select(User).where(User.extension_user_id == extension_user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Update last active
            user.last_active_at = datetime.utcnow()
            user.browser_info = browser_info
        else:
            # Create new user with A/B test assignment
            user = User(
                extension_user_id=extension_user_id,
                browser_info=browser_info,
                timezone=timezone,
                locale=locale,
                experiment_groups=self.assign_experiment_groups(extension_user_id)
            )
            self.db.add(user)
        
        await self.db.commit()
        return user
    
    async def process_event_batch(
        self,
        session_id: str,
        events: List[EventSchema],
        user_id: str
    ):
        """Process analytics events with deduplication and aggregation."""
        # Deduplicate events by hash
        seen_hashes = set()
        unique_events = []
        
        for event in events:
            event_hash = self.hash_event(event)
            if event_hash not in seen_hashes:
                seen_hashes.add(event_hash)
                unique_events.append(event)
        
        # Batch insert events
        event_models = []
        for event in unique_events:
            event_models.append(AnalyticsEvent(
                user_id=user_id,
                session_id=session_id,
                event_type=event.type,
                event_category=event.category,
                event_value=event.value,
                event_label=event.label,
                metadata=event.metadata,
                client_timestamp=event.client_timestamp,
                post_id=event.metadata.get('post_id') if event.metadata else None
            ))
        
        if event_models:
            self.db.add_all(event_models)
            await self.db.commit()
        
        # Update aggregated metrics asynchronously
        await self.update_aggregated_metrics(user_id, session_id, unique_events)
    
    async def update_aggregated_metrics(
        self,
        user_id: str,
        session_id: str,
        events: List[EventSchema]
    ):
        """Update user and session aggregated metrics."""
        # Calculate metrics from events
        metrics = self.calculate_metrics_from_events(events)
        
        # Update user metrics
        if metrics.get('avg_scroll_speed'):
            stmt = update(User).where(User.id == user_id).values(
                avg_scroll_speed=func.coalesce(
                    (User.avg_scroll_speed * User.total_posts_viewed + metrics['avg_scroll_speed']) / 
                    (User.total_posts_viewed + 1),
                    metrics['avg_scroll_speed']
                )
            )
            await self.db.execute(stmt)
        
        # Update session metrics
        if session_id:
            session_metrics = {
                'posts_viewed': metrics.get('posts_viewed', 0),
                'posts_analyzed': metrics.get('posts_analyzed', 0),
                'posts_interacted': metrics.get('posts_interacted', 0),
                'avg_scroll_speed': metrics.get('avg_scroll_speed'),
                'updated_at': datetime.utcnow()
            }
            
            stmt = update(UserSessionEnhanced).where(
                UserSessionEnhanced.id == session_id
            ).values(**session_metrics)
            await self.db.execute(stmt)
        
        await self.db.commit()
    
    @cache_result(ttl=300)  # Cache for 5 minutes
    async def get_user_dashboard(
        self,
        user_id: str,
        date_from: datetime,
        date_to: datetime
    ) -> Dict[str, Any]:
        """Generate user analytics dashboard with caching."""
        # Fetch user data
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Parallel queries for performance
        tasks = [
            self.get_interaction_stats(user_id, date_from, date_to),
            self.get_session_stats(user_id, date_from, date_to),
            self.get_chat_stats(user_id, date_from, date_to),
            self.get_accuracy_feedback(user_id, date_from, date_to)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            'user_id': user_id,
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'interaction_stats': results[0],
            'session_stats': results[1],
            'chat_stats': results[2],
            'accuracy_feedback': results[3],
            'behavior_metrics': {
                'avg_scroll_speed': user.avg_scroll_speed,
                'avg_posts_per_minute': user.avg_posts_per_minute,
                'total_posts_viewed': user.total_posts_viewed,
                'total_interactions': user.total_interactions
            }
        }
    
    def hash_event(self, event: EventSchema) -> str:
        """Generate hash for event deduplication."""
        hash_input = f"{event.type}:{event.client_timestamp}:{event.value}:{event.metadata}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def assign_experiment_groups(self, user_id: str) -> List[str]:
        """Assign user to A/B test groups deterministically."""
        groups = []
        
        # Hash-based assignment for consistency
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        
        # 50/50 split for metrics collection detail level
        if user_hash % 2 == 0:
            groups.append('detailed_metrics')
        else:
            groups.append('basic_metrics')
        
        # 20% get experimental features
        if user_hash % 5 == 0:
            groups.append('experimental_features')
        
        return groups
```

## Error Handling & Edge Cases

### Client-Side Error Handling

```typescript
// browser-extension/src/shared/logger.ts (used for error logging)
export class MetricsErrorHandler {
  private errorBuffer: ErrorEvent[] = [];
  private maxRetries: number = 3;
  private circuitBreaker: CircuitBreaker;
  
  constructor() {
    this.circuitBreaker = new CircuitBreaker({
      threshold: 5,
      timeout: 60000,
      resetTimeout: 120000
    });
  }
  
  async handleError(error: Error, context: ErrorContext): Promise<void> {
    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Metrics Error:', error, context);
    }
    
    // Check if metrics collection should be disabled
    if (this.circuitBreaker.isOpen()) {
      console.warn('Metrics collection temporarily disabled due to errors');
      return;
    }
    
    // Categorize error
    const errorCategory = this.categorizeError(error);
    
    switch (errorCategory) {
      case 'network':
        await this.handleNetworkError(error, context);
        break;
      case 'quota':
        await this.handleQuotaError(error, context);
        break;
      case 'validation':
        // Don't retry validation errors
        this.logError(error, context);
        break;
      default:
        await this.handleGenericError(error, context);
    }
  }
  
  private async handleNetworkError(error: Error, context: ErrorContext): Promise<void> {
    // Implement exponential backoff
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      await this.wait(Math.pow(2, attempt) * 1000);
      
      try {
        await context.retry();
        return;
      } catch (retryError) {
        if (attempt === this.maxRetries - 1) {
          this.circuitBreaker.recordFailure();
          this.bufferError(error, context);
        }
      }
    }
  }
  
  private async handleQuotaError(error: Error, context: ErrorContext): Promise<void> {
    // Storage quota exceeded - clear old data
    try {
      await this.clearOldMetrics();
      await context.retry();
    } catch (clearError) {
      console.error('Failed to clear old metrics:', clearError);
      // Disable metrics collection temporarily
      this.circuitBreaker.open();
    }
  }
  
  private bufferError(error: Error, context: ErrorContext): void {
    this.errorBuffer.push({
      timestamp: Date.now(),
      error: error.message,
      stack: error.stack,
      context
    });
    
    // Limit buffer size
    if (this.errorBuffer.length > 100) {
      this.errorBuffer.shift();
    }
  }
}
```

### Server-Side Error Handling

```python
# backend/core/error_handlers.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
import logging

logger = logging.getLogger(__name__)

async def database_error_handler(request: Request, exc: OperationalError):
    """Handle database connection errors."""
    logger.error(f"Database error: {exc}")
    
    # Check if it's a connection error
    if "connection" in str(exc).lower():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database temporarily unavailable",
                "retry_after": 30
            }
        )
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal database error"}
    )

async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle data integrity violations."""
    logger.warning(f"Integrity error: {exc}")
    
    # Check for duplicate key violations
    if "duplicate key" in str(exc).lower():
        return JSONResponse(
            status_code=409,
            content={"error": "Duplicate entry detected"}
        )
    
    # Check for foreign key violations
    if "foreign key" in str(exc).lower():
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid reference to related data"}
        )
    
    return JSONResponse(
        status_code=400,
        content={"error": "Data integrity violation"}
    )

class MetricsValidationError(Exception):
    """Custom exception for metrics validation errors."""
    pass

async def metrics_validation_error_handler(request: Request, exc: MetricsValidationError):
    """Handle metrics validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid metrics data",
            "detail": str(exc)
        }
    )
```

## Testing Strategy

### Unit Tests

```python
# backend/tests/test_analytics_service.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import asyncio

from services.analytics_service import AnalyticsService
from schemas.analytics import AnalyticsEvent

class TestAnalyticsService:
    @pytest.fixture
    async def service(self, async_session):
        return AnalyticsService(async_session)
    
    @pytest.mark.asyncio
    async def test_user_initialization_new_user(self, service):
        """Test creating a new user."""
        user = await service.initialize_user(
            extension_user_id="test_user_123",
            browser_info={"browser": "chrome", "version": "120"},
            timezone="America/New_York",
            locale="en_US"
        )
        
        assert user.extension_user_id == "test_user_123"
        assert user.experiment_groups is not None
        assert len(user.experiment_groups) > 0
    
    @pytest.mark.asyncio
    async def test_user_initialization_existing_user(self, service):
        """Test updating existing user."""
        # Create user first
        user1 = await service.initialize_user(
            extension_user_id="test_user_123",
            browser_info={"browser": "chrome", "version": "119"},
            timezone="America/New_York",
            locale="en_US"
        )
        
        # Update same user
        user2 = await service.initialize_user(
            extension_user_id="test_user_123",
            browser_info={"browser": "chrome", "version": "120"},
            timezone="America/New_York",
            locale="en_US"
        )
        
        assert user1.id == user2.id
        assert user2.browser_info["version"] == "120"
    
    @pytest.mark.asyncio
    async def test_event_deduplication(self, service):
        """Test that duplicate events are filtered."""
        events = [
            AnalyticsEvent(
                type="post_view",
                category="interaction",
                value=1.0,
                client_timestamp=datetime.utcnow(),
                metadata={"post_id": "123"}
            ),
            # Duplicate event
            AnalyticsEvent(
                type="post_view",
                category="interaction",
                value=1.0,
                client_timestamp=datetime.utcnow(),
                metadata={"post_id": "123"}
            ),
            # Different event
            AnalyticsEvent(
                type="post_click",
                category="interaction",
                value=2.0,
                client_timestamp=datetime.utcnow(),
                metadata={"post_id": "123"}
            )
        ]
        
        with patch.object(service, 'update_aggregated_metrics') as mock_update:
            await service.process_event_batch("session_123", events, "user_123")
            
            # Should only process 2 unique events
            call_args = mock_update.call_args[0]
            assert len(call_args[2]) == 2
    
    @pytest.mark.asyncio
    async def test_dashboard_caching(self, service):
        """Test that dashboard results are cached."""
        user_id = "test_user_123"
        date_from = datetime.utcnow() - timedelta(days=7)
        date_to = datetime.utcnow()
        
        with patch.object(service, 'get_interaction_stats') as mock_stats:
            mock_stats.return_value = {"clicks": 10}
            
            # First call should hit the database
            result1 = await service.get_user_dashboard(user_id, date_from, date_to)
            assert mock_stats.call_count == 1
            
            # Second call should use cache
            result2 = await service.get_user_dashboard(user_id, date_from, date_to)
            assert mock_stats.call_count == 1  # Still 1, used cache
            
            assert result1 == result2
```

### Integration Tests

```typescript
// browser-extension/src/content/metrics/MetricsCollector.test.ts
import { MetricsCollector } from '../../src/content/metrics/MetricsCollector';
import { MockServer } from '../mocks/MockServer';

describe('MetricsCollector Integration', () => {
  let collector: MetricsCollector;
  let mockServer: MockServer;
  
  beforeEach(() => {
    mockServer = new MockServer();
    collector = new MetricsCollector({
      batchSize: 10,
      flushInterval: 1000,
      enableDebugLogging: true,
      privacyMode: 'balanced'
    });
  });
  
  afterEach(() => {
    collector.destroy();
    mockServer.stop();
  });
  
  test('should batch events and send when threshold reached', async () => {
    mockServer.expectRequest('/api/v1/analytics/events', {
      method: 'POST',
      response: { status: 'ok' }
    });
    
    // Add events up to batch size
    for (let i = 0; i < 10; i++) {
      collector.trackEvent({
        type: 'test_event',
        category: 'test',
        value: i
      });
    }
    
    // Wait for automatic flush
    await new Promise(resolve => setTimeout(resolve, 100));
    
    expect(mockServer.getRequests()).toHaveLength(1);
    const request = mockServer.getRequests()[0];
    expect(request.body.events).toHaveLength(10);
  });
  
  test('should handle network errors with retry', async () => {
    let attempts = 0;
    mockServer.expectRequest('/api/v1/analytics/events', {
      method: 'POST',
      handler: () => {
        attempts++;
        if (attempts < 3) {
          return { status: 500, body: { error: 'Server error' } };
        }
        return { status: 200, body: { status: 'ok' } };
      }
    });
    
    collector.trackEvent({
      type: 'test_event',
      category: 'test'
    });
    
    await collector.flushEvents();
    
    expect(attempts).toBe(3);
  });
  
  test('should respect privacy mode settings', async () => {
    collector = new MetricsCollector({
      batchSize: 1,
      flushInterval: 1000,
      enableDebugLogging: false,
      privacyMode: 'strict'
    });
    
    mockServer.expectRequest('/api/v1/analytics/events', {
      method: 'POST',
      handler: (req) => {
        const event = req.body.events[0];
        expect(event.metadata.userAgent).toBeUndefined();
        expect(event.metadata.screenResolution).toBeUndefined();
        return { status: 200, body: { status: 'ok' } };
      }
    });
    
    collector.trackEvent({
      type: 'test_event',
      category: 'test',
      metadata: {
        userAgent: 'Chrome/120',
        screenResolution: '1920x1080',
        postId: '123'  // This should remain
      }
    });
    
    await collector.flushEvents();
  });
});
```

### End-to-End Tests

```python
# backend/tests/e2e/test_metrics_flow.py
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import asyncio

@pytest.mark.e2e
class TestMetricsFlow:
    @pytest.mark.asyncio
    async def test_complete_user_journey(self, async_client: AsyncClient):
        """Test complete metrics flow from user initialization to dashboard."""
        
        # 1. Initialize user
        init_response = await async_client.post(
            "/api/v1/analytics/users/initialize",
            json={
                "extension_user_id": "e2e_test_user",
                "browser_info": {"browser": "chrome", "version": "120"},
                "timezone": "UTC",
                "locale": "en_US",
                "client_ip": "127.0.0.1"
            }
        )
        assert init_response.status_code == 200
        user_data = init_response.json()
        user_id = user_data["user_id"]
        session_id = user_data["session_id"]
        
        # 2. Track post views
        for i in range(5):
            await async_client.post(
                f"/api/v1/analytics/posts/post_{i}/interactions",
                json={
                    "user_id": user_id,
                    "interaction_type": "viewed",
                    "backend_response_time_ms": 100 + i * 10,
                    "reading_time_ms": 5000 + i * 1000
                }
            )
        
        # 3. Submit event batch
        events = [
            {
                "type": "scroll_behavior",
                "category": "interaction",
                "value": 150.5,
                "client_timestamp": datetime.utcnow().isoformat(),
                "metadata": {"direction": "down"}
            },
            {
                "type": "icon_click",
                "category": "interaction",
                "value": 2000,
                "client_timestamp": datetime.utcnow().isoformat(),
                "metadata": {"post_id": "post_0"}
            }
        ]
        
        batch_response = await async_client.post(
            "/api/v1/analytics/events/batch",
            json={
                "session_id": session_id,
                "events": events
            }
        )
        assert batch_response.status_code == 200
        
        # 4. Wait for async processing
        await asyncio.sleep(1)
        
        # 5. Retrieve dashboard
        dashboard_response = await async_client.get(
            f"/api/v1/analytics/dashboard/{user_id}"
        )
        assert dashboard_response.status_code == 200
        dashboard = dashboard_response.json()
        
        # Verify metrics
        assert dashboard["interaction_stats"]["total_posts_viewed"] >= 5
        assert dashboard["behavior_metrics"]["total_interactions"] >= 1
        assert "detailed_metrics" in dashboard["user"]["experiment_groups"] or \
               "basic_metrics" in dashboard["user"]["experiment_groups"]
```

## Privacy & Compliance

### Privacy Controls Implementation

```typescript
// browser-extension/src/services/PrivacyManager.ts
export class PrivacyManager {
  private settings: PrivacySettings;
  private consentStatus: ConsentStatus;
  
  async initialize(): Promise<void> {
    // Load saved privacy settings
    this.settings = await this.loadSettings();
    
    // Check GDPR consent status
    if (this.isGDPRRegion()) {
      this.consentStatus = await this.checkConsentStatus();
      if (!this.consentStatus.hasConsent) {
        await this.requestConsent();
      }
    }
  }
  
  shouldCollectMetric(metricType: string): boolean {
    // Check if metric collection is allowed
    if (!this.consentStatus.hasConsent) {
      return false;
    }
    
    // Check privacy level
    switch (this.settings.privacyMode) {
      case 'strict':
        return this.isEssentialMetric(metricType);
      case 'balanced':
        return !this.isDetailedPersonalMetric(metricType);
      case 'full':
        return true;
      default:
        return false;
    }
  }
  
  async exportUserData(userId: string): Promise<UserDataExport> {
    // GDPR data portability
    const response = await fetch(`/api/v1/privacy/export/${userId}`);
    const data = await response.json();
    
    return {
      userData: data.user,
      events: data.events,
      interactions: data.interactions,
      exportedAt: new Date().toISOString()
    };
  }
  
  async deleteUserData(userId: string): Promise<void> {
    // GDPR right to deletion
    await fetch(`/api/v1/privacy/delete/${userId}`, {
      method: 'DELETE'
    });
    
    // Clear local storage
    localStorage.removeItem('ai-slop-user-id');
    localStorage.removeItem('ai-slop-metrics');
    
    // Reset collector
    this.metricsCollector.reset();
  }
  
  private isGDPRRegion(): boolean {
    const gdprCountries = ['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'PL'];
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    
    return gdprCountries.some(country => 
      timezone.includes(country) || navigator.language.startsWith(country.toLowerCase())
    );
  }
}
```

## Performance Considerations

### Database Optimization

```sql
-- Partitioning strategy for large tables
CREATE TABLE analytics_event_2025_01 PARTITION OF analytics_event
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE analytics_event_2025_02 PARTITION OF analytics_event
  FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Materialized views for common queries
CREATE MATERIALIZED VIEW user_daily_stats AS
SELECT 
  user_id,
  DATE(created_at) as date,
  COUNT(DISTINCT post_id) as posts_viewed,
  COUNT(CASE WHEN event_type = 'icon_click' THEN 1 END) as icon_clicks,
  AVG(event_value) FILTER (WHERE event_type = 'scroll_speed') as avg_scroll_speed
FROM analytics_event
WHERE created_at > CURRENT_DATE - INTERVAL '30 days'
GROUP BY user_id, DATE(created_at);

CREATE INDEX idx_user_daily_stats_user_date ON user_daily_stats(user_id, date);

-- Refresh materialized view daily
CREATE OR REPLACE FUNCTION refresh_user_stats()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY user_daily_stats;
END;
$$ LANGUAGE plpgsql;
```

### Caching Strategy

```python
# backend/utils/caching.py
from functools import wraps
import hashlib
import json
from typing import Any, Callable
import redis.asyncio as redis

redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

def cache_result(ttl: int = 300):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            cache_key = generate_cache_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result, default=str)
            )
            
            return result
        return wrapper
    return decorator

def generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate unique cache key."""
    key_parts = [func_name]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    
    key_string = ":".join(key_parts)
    return f"metrics:{hashlib.md5(key_string.encode()).hexdigest()}"
```

## Success Metrics & KPIs

### Technical KPIs
- **API Response Time**: P95 < 100ms, P99 < 200ms
- **Event Processing Latency**: < 5 seconds from client to database
- **Data Collection Success Rate**: > 99.5%
- **System Uptime**: > 99.9%
- **Database Query Performance**: P95 < 50ms

### Product KPIs
- **User Engagement Rate**: Increase by 15% within 3 months
- **Chat Completion Rate**: > 70% of started chats
- **Feature Adoption**: > 60% of users interact with AI detection icons
- **User Retention**: 10% improvement in 30-day retention
- **Detection Accuracy Feedback**: > 85% positive feedback

### Business KPIs
- **False Positive Rate**: Reduce by 25% through feedback loop
- **User Satisfaction Score**: Increase NPS by 20 points
- **Data-Driven Decisions**: 100% of new features backed by metrics
- **Cost Efficiency**: < $0.001 per user per day for analytics infrastructure

## Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)
- [ ] Database schema migration script
- [ ] User and session management APIs
- [ ] Basic event collection infrastructure
- [ ] Privacy consent framework

### Phase 2: Core Metrics (Weeks 3-4)
- [ ] Post interaction tracking
- [ ] Scroll and reading behavior metrics
- [ ] Event batching and deduplication
- [ ] Error handling and retry logic

### Phase 3: Advanced Analytics (Weeks 5-6)
- [ ] Chat session tracking
- [ ] Real-time event processing pipeline
- [ ] Dashboard API endpoints
- [ ] Performance monitoring

### Phase 4: Optimization & Polish (Weeks 7-8)
- [ ] Caching layer implementation
- [ ] Database query optimization
- [ ] Privacy controls UI
- [ ] A/B testing framework
- [ ] Documentation and training

## Monitoring & Alerting

### Key Alerts
```yaml
# monitoring/alerts.yaml
alerts:
  - name: HighAPILatency
    condition: p95_response_time > 200ms
    duration: 5m
    severity: warning
    
  - name: LowEventIngestionRate
    condition: events_per_minute < 100
    duration: 10m
    severity: warning
    
  - name: DatabaseConnectionPoolExhausted
    condition: available_connections < 5
    duration: 2m
    severity: critical
    
  - name: HighErrorRate
    condition: error_rate > 0.01
    duration: 5m
    severity: warning
    
  - name: StorageQuotaWarning
    condition: storage_used_percentage > 80
    duration: 1h
    severity: warning
```

This comprehensive plan provides a production-ready implementation strategy for sophisticated user behavior analytics with proper error handling, testing, privacy compliance, and performance optimization.
