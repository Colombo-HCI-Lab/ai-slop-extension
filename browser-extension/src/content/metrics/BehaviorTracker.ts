/**
 * Comprehensive user behavior tracking including mouse patterns, attention metrics,
 * and engagement depth analysis
 */

import type { 
  MouseHoverData, 
  AttentionMetrics, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';

const logger = createLogger('BehaviorTracker');

interface MouseState {
  x: number;
  y: number;
  timestamp: number;
}

interface ElementAttention {
  element: Element;
  focusTime: number;
  entryTime: number;
  scrollDepth: number;
  characterCount: number;
}

interface RageClickData {
  count: number;
  timeWindow: number;
  lastClick: number;
  position: { x: number; y: number };
}

export class BehaviorTracker {
  private mouseTrail: MouseState[] = [];
  private hoverData: Map<string, MouseHoverData> = new Map();
  private attentionMap: Map<string, ElementAttention> = new Map();
  private rageClickDetector: RageClickData = { count: 0, timeWindow: 2000, lastClick: 0, position: { x: 0, y: 0 } };
  
  private currentFocusElement: Element | null = null;
  private focusStartTime = 0;
  private totalFocusTime = 0;
  private totalBlurTime = 0;
  private lastActivityTime = Date.now();
  
  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  // Performance optimization
  private mouseThrottleTimer: number | null = null;
  private scrollThrottleTimer: number | null = null;
  
  constructor(config: EnhancedMetricsConfig, eventCallback: (event: UnifiedAnalyticsEvent) => void) {
    this.config = config;
    this.eventCallback = eventCallback;
    
    if (config.enableMouseTracking) {
      this.initializeMouseTracking();
    }
    
    this.initializeAttentionTracking();
    this.initializeEngagementTracking();
  }

  private initializeMouseTracking(): void {
    // Mouse movement tracking with sampling
    document.addEventListener('mousemove', (event) => {
      if (Math.random() > this.config.samplingRates.mouse) return;
      
      if (this.mouseThrottleTimer) return;
      
      this.mouseThrottleTimer = window.setTimeout(() => {
        this.trackMouseMovement(event);
        this.mouseThrottleTimer = null;
      }, 50); // 20fps max
    }, { passive: true });

    // Hover tracking
    document.addEventListener('mouseover', this.handleMouseOver.bind(this), true);
    document.addEventListener('mouseout', this.handleMouseOut.bind(this), true);

    // Click tracking for rage detection
    document.addEventListener('click', this.handleClick.bind(this), true);
  }

  private initializeAttentionTracking(): void {
    // Focus and blur tracking
    window.addEventListener('focus', this.handleWindowFocus.bind(this));
    window.addEventListener('blur', this.handleWindowBlur.bind(this));

    // Element focus tracking using intersection observer
    const observer = new IntersectionObserver(
      this.handleElementVisibility.bind(this),
      { threshold: [0.1, 0.5, 0.8] }
    );

    // Observe all post elements
    const observeNewPosts = () => {
      document.querySelectorAll('[data-post-id]').forEach(post => {
        if (!this.attentionMap.has(post.getAttribute('data-post-id')!)) {
          observer.observe(post);
        }
      });
    };

    // Initial observation
    observeNewPosts();
    
    // Watch for new posts
    const postObserver = new MutationObserver(observeNewPosts);
    postObserver.observe(document.body, { 
      childList: true, 
      subtree: true 
    });
  }

  private initializeEngagementTracking(): void {
    // Reading speed calculation
    document.addEventListener('scroll', () => {
      if (this.scrollThrottleTimer) return;
      
      this.scrollThrottleTimer = window.setTimeout(() => {
        this.calculateReadingMetrics();
        this.scrollThrottleTimer = null;
      }, 100);
    }, { passive: true });

    // Copy action tracking
    document.addEventListener('copy', this.handleCopyAction.bind(this));
    
    // Selection tracking for engagement depth
    document.addEventListener('selectionchange', this.handleTextSelection.bind(this));
  }

  private trackMouseMovement(event: MouseEvent): void {
    const now = Date.now();
    const state: MouseState = {
      x: event.clientX,
      y: event.clientY,
      timestamp: now
    };

    this.mouseTrail.push(state);
    
    // Keep only last 50 points to manage memory
    if (this.mouseTrail.length > 50) {
      this.mouseTrail.shift();
    }

    // Analyze mouse patterns periodically
    if (this.mouseTrail.length > 10 && this.mouseTrail.length % 10 === 0) {
      this.analyzeMousePatterns();
    }
  }

  private handleMouseOver(event: Event): void {
    const target = event.target as Element;
    const postId = this.getPostId(target);
    if (!postId) return;

    const elementId = this.getElementId(target);
    const now = Date.now();

    const hoverData: MouseHoverData = {
      elementId,
      hoverDuration: 0,
      entryTime: now,
      exitTime: 0,
      elementBounds: target.getBoundingClientRect(),
      mouseTrail: [...this.mouseTrail.slice(-10)] // Last 10 points
    };

    this.hoverData.set(elementId, hoverData);
  }

  private handleMouseOut(event: Event): void {
    const target = event.target as Element;
    const elementId = this.getElementId(target);
    const hoverData = this.hoverData.get(elementId);
    
    if (!hoverData) return;

    const now = Date.now();
    hoverData.exitTime = now;
    hoverData.hoverDuration = now - hoverData.entryTime;

    // Track meaningful hovers (>500ms)
    if (hoverData.hoverDuration > 500) {
      this.eventCallback({
        event_type: 'mouse_hover_pattern',
        event_category: 'behavior',
        event_priority: 'medium',
        post_id: this.getPostId(target),
        event_data: {
          element_id: elementId,
          hover_duration_ms: hoverData.hoverDuration,
          element_type: target.tagName.toLowerCase(),
          element_bounds: {
            width: hoverData.elementBounds.width,
            height: hoverData.elementBounds.height
          },
          mouse_trail_length: hoverData.mouseTrail.length,
          engagement_level: this.calculateEngagementLevel(hoverData.hoverDuration)
        },
        client_timestamp: new Date().toISOString()
      });
    }

    this.hoverData.delete(elementId);
  }

  private handleClick(event: MouseEvent): void {
    const now = Date.now();
    const clickPosition = { x: event.clientX, y: event.clientY };
    
    // Check for rage clicking (multiple rapid clicks in same area)
    const timeSinceLastClick = now - this.rageClickDetector.lastClick;
    const distanceFromLastClick = Math.sqrt(
      Math.pow(clickPosition.x - this.rageClickDetector.position.x, 2) +
      Math.pow(clickPosition.y - this.rageClickDetector.position.y, 2)
    );

    if (timeSinceLastClick < this.rageClickDetector.timeWindow && distanceFromLastClick < 50) {
      this.rageClickDetector.count++;
      
      if (this.rageClickDetector.count >= 3) {
        this.eventCallback({
          event_type: 'rage_click_detected',
          event_category: 'behavior',
          event_priority: 'high',
          post_id: this.getPostId(event.target as Element),
          event_data: {
            click_count: this.rageClickDetector.count,
            time_window_ms: this.rageClickDetector.timeWindow,
            position: clickPosition,
            frustration_level: Math.min(this.rageClickDetector.count / 3, 3)
          },
          client_timestamp: new Date().toISOString()
        });
        
        this.rageClickDetector.count = 0; // Reset
      }
    } else {
      this.rageClickDetector.count = 1;
    }

    this.rageClickDetector.lastClick = now;
    this.rageClickDetector.position = clickPosition;
  }

  private handleWindowFocus(): void {
    this.focusStartTime = Date.now();
    
    this.eventCallback({
      event_type: 'attention_focus',
      event_category: 'behavior',
      event_priority: 'medium',
      event_data: {
        focus_type: 'window',
        timestamp: this.focusStartTime
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleWindowBlur(): void {
    const now = Date.now();
    if (this.focusStartTime > 0) {
      const focusSession = now - this.focusStartTime;
      this.totalFocusTime += focusSession;
      
      this.eventCallback({
        event_type: 'attention_blur',
        event_category: 'behavior', 
        event_priority: 'medium',
        event_data: {
          blur_type: 'window',
          session_focus_time_ms: focusSession,
          total_focus_time_ms: this.totalFocusTime,
          timestamp: now
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private handleElementVisibility(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      const postId = entry.target.getAttribute('data-post-id');
      if (!postId) return;

      const now = Date.now();

      if (entry.isIntersecting) {
        // Element entered viewport
        const attention: ElementAttention = {
          element: entry.target,
          focusTime: 0,
          entryTime: now,
          scrollDepth: entry.intersectionRatio,
          characterCount: this.getTextLength(entry.target)
        };
        
        this.attentionMap.set(postId, attention);
      } else {
        // Element left viewport
        const attention = this.attentionMap.get(postId);
        if (attention) {
          attention.focusTime = now - attention.entryTime;
          
          // Calculate reading speed
          const readingSpeed = attention.characterCount > 0 
            ? (attention.characterCount / (attention.focusTime / 1000)) 
            : 0;

          this.eventCallback({
            event_type: 'content_engagement_depth',
            event_category: 'behavior',
            event_priority: 'medium',
            post_id: postId,
            event_data: {
              focus_time_ms: attention.focusTime,
              character_count: attention.characterCount,
              reading_speed_chars_per_sec: readingSpeed,
              scroll_depth_percentage: Math.round(attention.scrollDepth * 100),
              engagement_quality: this.assessEngagementQuality(attention),
              completion_estimate: this.estimateContentCompletion(attention)
            },
            client_timestamp: new Date().toISOString()
          });

          this.attentionMap.delete(postId);
        }
      }
    });
  }

  private handleCopyAction(event: ClipboardEvent): void {
    const selection = window.getSelection();
    const selectedText = selection?.toString() || '';
    const target = event.target as Element;
    
    this.eventCallback({
      event_type: 'copy_action',
      event_category: 'behavior',
      event_priority: 'high',
      post_id: this.getPostId(target),
      event_data: {
        text_length: selectedText.length,
        has_detected_content: this.hasAIDetectionIcon(target),
        copy_source: target.tagName.toLowerCase(),
        interaction_confidence: selectedText.length > 20 ? 'high' : 'low'
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleTextSelection(): void {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();
    
    if (selectedText.length > 10) { // Meaningful selection
      const container = range.commonAncestorContainer;
      const element = container.nodeType === Node.TEXT_NODE 
        ? container.parentElement 
        : container as Element;
      
      this.eventCallback({
        event_type: 'text_selection',
        event_category: 'behavior',
        event_priority: 'medium',
        post_id: this.getPostId(element),
        event_data: {
          text_length: selectedText.length,
          selection_type: range.collapsed ? 'cursor' : 'text',
          has_detected_content: this.hasAIDetectionIcon(element)
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private analyzeMousePatterns(): void {
    if (this.mouseTrail.length < 5) return;

    const recent = this.mouseTrail.slice(-10);
    const totalDistance = this.calculateMouseDistance(recent);
    const averageSpeed = this.calculateAverageSpeed(recent);
    const directionChanges = this.countDirectionChanges(recent);
    const isErratic = directionChanges > recent.length * 0.7;

    this.eventCallback({
      event_type: 'mouse_movement_pattern',
      event_category: 'behavior',
      event_priority: 'low',
      event_data: {
        total_distance: totalDistance,
        average_speed: averageSpeed,
        direction_changes: directionChanges,
        is_erratic_movement: isErratic,
        sample_size: recent.length,
        pattern_type: this.classifyMovementPattern(averageSpeed, directionChanges, isErratic)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private calculateReadingMetrics(): void {
    // Calculate reading patterns based on scroll behavior
    const currentScroll = window.scrollY;
    const viewportHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    
    const scrollPercentage = (currentScroll + viewportHeight) / documentHeight;
    
    this.eventCallback({
      event_type: 'reading_behavior_pattern',
      event_category: 'behavior', 
      event_priority: 'low',
      event_data: {
        scroll_percentage: Math.round(scrollPercentage * 100),
        viewport_height: viewportHeight,
        scroll_position: currentScroll,
        reading_pace: this.calculateReadingPace(),
        active_attention_spans: this.attentionMap.size
      },
      client_timestamp: new Date().toISOString()
    });
  }

  // Helper methods
  private getPostId(element: Element | null): string | undefined {
    if (!element) return undefined;
    return element.closest('[data-post-id]')?.getAttribute('data-post-id') || undefined;
  }

  private getElementId(element: Element): string {
    return element.id || `${element.tagName.toLowerCase()}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  }

  private getTextLength(element: Element): number {
    return element.textContent?.length || 0;
  }

  private hasAIDetectionIcon(element: Element | null): boolean {
    return !!element?.closest('[data-post-id]')?.querySelector('.ai-detection-icon');
  }

  private calculateEngagementLevel(duration: number): 'low' | 'medium' | 'high' {
    if (duration < 1000) return 'low';
    if (duration < 5000) return 'medium';
    return 'high';
  }

  private assessEngagementQuality(attention: ElementAttention): 'shallow' | 'moderate' | 'deep' {
    const timePerChar = attention.characterCount > 0 ? attention.focusTime / attention.characterCount : 0;
    
    if (timePerChar < 10) return 'shallow'; // Very fast scanning
    if (timePerChar < 50) return 'moderate'; // Normal reading
    return 'deep'; // Careful reading or re-reading
  }

  private estimateContentCompletion(attention: ElementAttention): number {
    // Rough estimate based on scroll depth and time spent
    const timeBasedCompletion = Math.min(attention.focusTime / 5000, 1); // 5s = 100%
    const scrollBasedCompletion = attention.scrollDepth;
    
    return Math.round(Math.max(timeBasedCompletion, scrollBasedCompletion) * 100);
  }

  private calculateMouseDistance(trail: MouseState[]): number {
    let totalDistance = 0;
    for (let i = 1; i < trail.length; i++) {
      const prev = trail[i - 1];
      const curr = trail[i];
      totalDistance += Math.sqrt(
        Math.pow(curr.x - prev.x, 2) + Math.pow(curr.y - prev.y, 2)
      );
    }
    return totalDistance;
  }

  private calculateAverageSpeed(trail: MouseState[]): number {
    if (trail.length < 2) return 0;
    
    const totalDistance = this.calculateMouseDistance(trail);
    const totalTime = trail[trail.length - 1].timestamp - trail[0].timestamp;
    
    return totalTime > 0 ? totalDistance / totalTime : 0;
  }

  private countDirectionChanges(trail: MouseState[]): number {
    if (trail.length < 3) return 0;
    
    let changes = 0;
    let lastDirection = { x: 0, y: 0 };
    
    for (let i = 1; i < trail.length - 1; i++) {
      const current = trail[i];
      const next = trail[i + 1];
      const direction = {
        x: next.x - current.x,
        y: next.y - current.y
      };
      
      if (i > 1) {
        const xChange = Math.sign(direction.x) !== Math.sign(lastDirection.x);
        const yChange = Math.sign(direction.y) !== Math.sign(lastDirection.y);
        if (xChange || yChange) changes++;
      }
      
      lastDirection = direction;
    }
    
    return changes;
  }

  private classifyMovementPattern(speed: number, changes: number, isErratic: boolean): string {
    if (isErratic) return 'erratic';
    if (speed > 1000) return 'fast_scanning';
    if (speed < 100) return 'deliberate';
    if (changes > 5) return 'exploratory';
    return 'normal';
  }

  private calculateReadingPace(): 'slow' | 'normal' | 'fast' {
    // Simple heuristic based on recent activity
    const recentActivity = Date.now() - this.lastActivityTime;
    if (recentActivity > 3000) return 'slow';
    if (recentActivity < 1000) return 'fast';
    return 'normal';
  }

  public destroy(): void {
    if (this.mouseThrottleTimer) clearTimeout(this.mouseThrottleTimer);
    if (this.scrollThrottleTimer) clearTimeout(this.scrollThrottleTimer);
    
    // Clear data
    this.mouseTrail = [];
    this.hoverData.clear();
    this.attentionMap.clear();
  }
}