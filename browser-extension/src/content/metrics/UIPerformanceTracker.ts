/**
 * UI/UX Performance and Interaction Analytics Tracker
 * Monitors render performance, visual hierarchy effectiveness, and error recovery patterns
 */

import type { 
  PerformanceMetrics, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';

const logger = createLogger('UIPerformanceTracker');

interface RenderPerformance {
  elementType: string;
  renderStart: number;
  renderEnd: number;
  renderDuration: number;
  domReady: number;
  firstPaint: number;
  layoutShifts: number;
}

interface TooltipInteraction {
  elementId: string;
  showTime: number;
  hideTime: number;
  duration: number;
  dismissMethod: 'timeout' | 'click' | 'scroll' | 'hover_out';
  interactionDepth: 'surface' | 'engaged' | 'deep';
}

interface ErrorRecovery {
  errorType: string;
  errorMessage: string;
  recoveryAction: string;
  recoveryTime: number;
  userInitiated: boolean;
  successful: boolean;
}

interface VisualHierarchy {
  elementType: string;
  position: { x: number; y: number; width: number; height: number };
  attentionScore: number;
  interactionRate: number;
  visibilityDuration: number;
}

export class UIPerformanceTracker {
  private performanceObserver: PerformanceObserver | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private renderTimings: Map<string, RenderPerformance> = new Map();
  private tooltipInteractions: Map<string, TooltipInteraction> = new Map();
  private errorHistory: ErrorRecovery[] = [];
  private visualElements: Map<string, VisualHierarchy> = new Map();
  
  private memoryUsageBaseline = 0;
  private lastLayoutShift = 0;
  private cumulativeLayoutShift = 0;

  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  constructor(config: EnhancedMetricsConfig, eventCallback: (event: UnifiedAnalyticsEvent) => void) {
    this.config = config;
    this.eventCallback = eventCallback;
    
    this.initializePerformanceTracking();
    this.initializeUIInteractionTracking();
    this.initializeErrorTracking();
    this.initializeVisualHierarchyTracking();
  }

  private initializePerformanceTracking(): void {
    if (!this.config.enablePerformanceTracking) return;

    // Performance Observer for various metrics
    try {
      this.performanceObserver = new PerformanceObserver((list) => {
        list.getEntries().forEach(entry => {
          this.processPerformanceEntry(entry);
        });
      });

      // Observe different performance entry types
      const supportedTypes = ['measure', 'navigation', 'paint', 'layout-shift'];
      supportedTypes.forEach(type => {
        try {
          this.performanceObserver!.observe({ entryTypes: [type] });
        } catch (e) {
          // Some types might not be supported
        }
      });
    } catch (error) {
      logger.warn('Performance Observer not supported:', error);
    }

    // Memory usage tracking
    this.trackMemoryUsage();
    setInterval(() => this.trackMemoryUsage(), 30000); // Every 30 seconds

    // Layout shift tracking
    this.initializeLayoutShiftTracking();
  }

  private initializeUIInteractionTracking(): void {
    // Track tooltip interactions
    document.addEventListener('mouseenter', (event) => {
      const target = event.target as Element;
      if (this.isTooltipTrigger(target)) {
        this.startTooltipInteraction(target);
      }
    });

    document.addEventListener('mouseleave', (event) => {
      const target = event.target as Element;
      if (this.isTooltipTrigger(target)) {
        this.endTooltipInteraction(target, 'hover_out');
      }
    });

    // Track window resize behavior
    this.initializeResizeTracking();
    
    // Track scroll interactions with UI elements
    document.addEventListener('scroll', this.handleScrollInteraction.bind(this), { passive: true });
  }

  private initializeErrorTracking(): void {
    // Global error handler
    window.addEventListener('error', (event) => {
      this.trackError('javascript_error', event.message, event);
    });

    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.trackError('promise_rejection', event.reason?.toString() || 'Unknown promise rejection', event);
    });

    // Custom error tracking for extension-specific errors
    this.setupCustomErrorTracking();
  }

  private initializeVisualHierarchyTracking(): void {
    // Intersection Observer for visual hierarchy
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          this.updateVisualHierarchy(entry);
        });
      },
      { threshold: [0, 0.25, 0.5, 0.75, 1.0] }
    );

    // Observe key UI elements
    const observeUIElements = () => {
      const selectors = [
        '.ai-detection-icon',
        '.chat-window',
        '.tooltip',
        '.notification',
        '.modal'
      ];

      selectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(element => {
          observer.observe(element);
        });
      });
    };

    observeUIElements();
    
    // Watch for new elements
    const mutationObserver = new MutationObserver(observeUIElements);
    mutationObserver.observe(document.body, { childList: true, subtree: true });
  }

  public trackIconRenderPerformance(postId: string, iconElement: Element): void {
    const renderStart = performance.now();
    
    // Use requestAnimationFrame to measure when icon is actually rendered
    requestAnimationFrame(() => {
      const renderEnd = performance.now();
      const renderDuration = renderEnd - renderStart;

      const renderPerf: RenderPerformance = {
        elementType: 'ai_detection_icon',
        renderStart,
        renderEnd,
        renderDuration,
        domReady: renderEnd,
        firstPaint: renderEnd,
        layoutShifts: this.cumulativeLayoutShift - this.lastLayoutShift
      };

      this.renderTimings.set(postId, renderPerf);
      this.lastLayoutShift = this.cumulativeLayoutShift;

      this.eventCallback({
        event_type: 'icon_render_performance',
        event_category: 'ui',
        event_priority: 'medium',
        post_id: postId,
        event_data: {
          render_duration_ms: renderDuration,
          render_efficiency: this.assessRenderEfficiency(renderDuration),
          layout_shifts: renderPerf.layoutShifts,
          element_complexity: this.assessElementComplexity(iconElement),
          performance_grade: this.gradePerformance(renderDuration),
          viewport_position: this.getViewportPosition(iconElement)
        },
        client_timestamp: new Date().toISOString()
      });
    });
  }

  public trackChatWindowResize(windowElement: Element, resizeData: { width: number; height: number }): void {
    this.eventCallback({
      event_type: 'chat_resize_behavior',
      event_category: 'ui',
      event_priority: 'medium',
      event_data: {
        new_width: resizeData.width,
        new_height: resizeData.height,
        resize_ratio: resizeData.width / resizeData.height,
        resize_trigger: 'user_action',
        window_state: this.getChatWindowState(windowElement),
        user_preference_indication: this.analyzeResizePreference(resizeData),
        optimal_size_deviation: this.calculateOptimalSizeDeviation(resizeData)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public trackErrorRecovery(errorType: string, recoveryAction: string, successful: boolean): void {
    const recovery: ErrorRecovery = {
      errorType,
      errorMessage: '',
      recoveryAction,
      recoveryTime: performance.now(),
      userInitiated: true,
      successful
    };

    this.errorHistory.push(recovery);

    this.eventCallback({
      event_type: 'error_recovery_flow',
      event_category: 'ui',
      event_priority: 'high',
      event_data: {
        error_type: errorType,
        recovery_action: recoveryAction,
        recovery_successful: successful,
        recovery_time_ms: recovery.recoveryTime,
        error_frequency: this.calculateErrorFrequency(errorType),
        user_recovery_rate: this.calculateUserRecoveryRate(),
        system_resilience_score: this.calculateResilienceScore()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private processPerformanceEntry(entry: PerformanceEntry): void {
    switch (entry.entryType) {
      case 'layout-shift':
        this.handleLayoutShift(entry as any);
        break;
      case 'paint':
        this.handlePaintTiming(entry);
        break;
      case 'measure':
        this.handleCustomMeasure(entry);
        break;
      case 'navigation':
        this.handleNavigationTiming(entry as PerformanceNavigationTiming);
        break;
    }
  }

  private handleLayoutShift(entry: any): void {
    if (!entry.hadRecentInput) {
      this.cumulativeLayoutShift += entry.value;
      
      this.eventCallback({
        event_type: 'layout_shift_detected',
        event_category: 'ui',
        event_priority: 'medium',
        event_data: {
          shift_value: entry.value,
          cumulative_shift: this.cumulativeLayoutShift,
          shift_severity: this.categorizeCLS(entry.value),
          affected_elements: entry.sources?.length || 0,
          user_initiated: entry.hadRecentInput
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private handlePaintTiming(entry: PerformanceEntry): void {
    this.eventCallback({
      event_type: 'paint_timing',
      event_category: 'performance',
      event_priority: 'low',
      event_data: {
        paint_type: entry.name,
        timing_ms: entry.startTime,
        performance_budget_status: entry.startTime < 1000 ? 'within_budget' : 'over_budget'
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private startTooltipInteraction(element: Element): void {
    const elementId = this.getElementId(element);
    const now = performance.now();

    const interaction: TooltipInteraction = {
      elementId,
      showTime: now,
      hideTime: 0,
      duration: 0,
      dismissMethod: 'timeout',
      interactionDepth: 'surface'
    };

    this.tooltipInteractions.set(elementId, interaction);
  }

  private endTooltipInteraction(element: Element, dismissMethod: TooltipInteraction['dismissMethod']): void {
    const elementId = this.getElementId(element);
    const interaction = this.tooltipInteractions.get(elementId);
    
    if (!interaction) return;

    const now = performance.now();
    interaction.hideTime = now;
    interaction.duration = now - interaction.showTime;
    interaction.dismissMethod = dismissMethod;
    interaction.interactionDepth = this.assessTooltipDepth(interaction.duration);

    this.eventCallback({
      event_type: 'tooltip_interaction_depth',
      event_category: 'ui',
      event_priority: 'medium',
      event_data: {
        element_id: elementId,
        show_duration_ms: interaction.duration,
        dismiss_method: dismissMethod,
        interaction_depth: interaction.interactionDepth,
        tooltip_effectiveness: this.assessTooltipEffectiveness(interaction),
        user_engagement_signal: interaction.duration > 2000 ? 'high' : 'low'
      },
      client_timestamp: new Date().toISOString()
    });

    this.tooltipInteractions.delete(elementId);
  }

  private trackMemoryUsage(): void {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      const currentUsage = memory.usedJSHeapSize;
      
      if (this.memoryUsageBaseline === 0) {
        this.memoryUsageBaseline = currentUsage;
      }

      const memoryIncrease = currentUsage - this.memoryUsageBaseline;
      const memoryPressure = currentUsage / memory.totalJSHeapSize;

      this.eventCallback({
        event_type: 'memory_usage_tracking',
        event_category: 'performance',
        event_priority: 'low',
        event_data: {
          current_usage_mb: Math.round(currentUsage / 1024 / 1024),
          baseline_usage_mb: Math.round(this.memoryUsageBaseline / 1024 / 1024),
          memory_increase_mb: Math.round(memoryIncrease / 1024 / 1024),
          memory_pressure: Math.round(memoryPressure * 100),
          memory_efficiency: this.assessMemoryEfficiency(memoryIncrease),
          gc_needed: memoryPressure > 0.8
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private initializeLayoutShiftTracking(): void {
    try {
      const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach(entry => {
          this.handleLayoutShift(entry);
        });
      });
      observer.observe({ entryTypes: ['layout-shift'] });
    } catch (error) {
      // Layout shift API not supported
    }
  }

  private initializeResizeTracking(): void {
    this.resizeObserver = new ResizeObserver((entries) => {
      entries.forEach(entry => {
        if (entry.target.classList.contains('chat-window')) {
          const rect = entry.contentRect;
          this.trackChatWindowResize(entry.target, { 
            width: rect.width, 
            height: rect.height 
          });
        }
      });
    });

    // Observe chat windows
    document.querySelectorAll('.chat-window').forEach(element => {
      this.resizeObserver!.observe(element);
    });
  }

  private handleScrollInteraction(): void {
    // Track scroll behavior affecting UI elements
    const visibleTooltips = Array.from(this.tooltipInteractions.keys())
      .map(id => document.getElementById(id))
      .filter(Boolean);

    visibleTooltips.forEach(tooltip => {
      this.endTooltipInteraction(tooltip!, 'scroll');
    });
  }

  private setupCustomErrorTracking(): void {
    // Override console.error to catch extension-specific errors
    const originalError = console.error;
    console.error = (...args) => {
      this.trackError('console_error', args.join(' '), { args });
      originalError.apply(console, args);
    };
  }

  private trackError(type: string, message: string, context: any): void {
    this.eventCallback({
      event_type: 'ui_error_detected',
      event_category: 'ui',
      event_priority: 'critical',
      event_data: {
        error_type: type,
        error_message: message,
        error_context: typeof context === 'object' ? JSON.stringify(context).slice(0, 500) : String(context),
        error_frequency: this.calculateErrorFrequency(type),
        stack_trace: context?.stack?.slice(0, 1000) || '',
        user_action_before_error: this.getLastUserAction(),
        recovery_possible: this.assessRecoveryPossibility(type)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private updateVisualHierarchy(entry: IntersectionObserverEntry): void {
    const element = entry.target;
    const elementId = this.getElementId(element);
    
    let hierarchy = this.visualElements.get(elementId);
    if (!hierarchy) {
      hierarchy = {
        elementType: element.className || element.tagName.toLowerCase(),
        position: element.getBoundingClientRect(),
        attentionScore: 0,
        interactionRate: 0,
        visibilityDuration: 0
      };
      this.visualElements.set(elementId, hierarchy);
    }

    // Update attention score based on visibility
    if (entry.isIntersecting) {
      hierarchy.attentionScore += entry.intersectionRatio * 10;
      
      this.eventCallback({
        event_type: 'visual_hierarchy_effectiveness',
        event_category: 'ui',
        event_priority: 'low',
        event_data: {
          element_type: hierarchy.elementType,
          attention_score: hierarchy.attentionScore,
          intersection_ratio: entry.intersectionRatio,
          position_score: this.calculatePositionScore(hierarchy.position),
          visibility_optimization: this.assessVisibilityOptimization(entry)
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  // Helper methods
  private isTooltipTrigger(element: Element): boolean {
    return element.hasAttribute('data-tooltip') ||
           element.classList.contains('tooltip-trigger') ||
           element.querySelector('.tooltip') !== null;
  }

  private getElementId(element: Element): string {
    return element.id || 
           `${element.tagName.toLowerCase()}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  }

  private assessRenderEfficiency(duration: number): string {
    if (duration < 50) return 'excellent';
    if (duration < 100) return 'good';
    if (duration < 200) return 'fair';
    return 'poor';
  }

  private assessElementComplexity(element: Element): number {
    const childCount = element.children.length;
    const styleCount = element.getAttribute('style')?.split(';').length || 0;
    const classCount = element.classList.length;
    
    return Math.min((childCount + styleCount + classCount) / 10, 5);
  }

  private gradePerformance(duration: number): string {
    if (duration < 16) return 'A+'; // 60fps
    if (duration < 33) return 'A';  // 30fps
    if (duration < 50) return 'B';  // 20fps
    if (duration < 100) return 'C';
    return 'D';
  }

  private getViewportPosition(element: Element): { top: number; left: number; inView: boolean } {
    const rect = element.getBoundingClientRect();
    const inView = rect.top >= 0 && rect.left >= 0 && 
                   rect.bottom <= window.innerHeight && rect.right <= window.innerWidth;
    
    return { top: rect.top, left: rect.left, inView };
  }

  private getChatWindowState(element: Element): string {
    if (element.classList.contains('minimized')) return 'minimized';
    if (element.classList.contains('maximized')) return 'maximized';
    return 'normal';
  }

  private analyzeResizePreference(size: { width: number; height: number }): string {
    const ratio = size.width / size.height;
    
    if (ratio > 2) return 'prefers_wide';
    if (ratio < 0.8) return 'prefers_tall';
    return 'balanced';
  }

  private calculateOptimalSizeDeviation(size: { width: number; height: number }): number {
    const optimalWidth = 400;
    const optimalHeight = 600;
    
    const widthDeviation = Math.abs(size.width - optimalWidth) / optimalWidth;
    const heightDeviation = Math.abs(size.height - optimalHeight) / optimalHeight;
    
    return Math.round((widthDeviation + heightDeviation) * 50);
  }

  private calculateErrorFrequency(errorType: string): number {
    const recent = this.errorHistory
      .filter(e => e.errorType === errorType && Date.now() - e.recoveryTime < 300000)
      .length;
    
    return recent;
  }

  private calculateUserRecoveryRate(): number {
    if (this.errorHistory.length === 0) return 1;
    
    const successfulRecoveries = this.errorHistory.filter(e => e.successful).length;
    return successfulRecoveries / this.errorHistory.length;
  }

  private calculateResilienceScore(): number {
    const recoveryRate = this.calculateUserRecoveryRate();
    const errorFrequency = this.errorHistory.length;
    
    return Math.max(0, 1 - (errorFrequency * 0.1) + (recoveryRate * 0.5));
  }

  private categorizeCLS(value: number): string {
    if (value < 0.1) return 'good';
    if (value < 0.25) return 'needs_improvement';
    return 'poor';
  }

  private assessTooltipDepth(duration: number): TooltipInteraction['interactionDepth'] {
    if (duration < 1000) return 'surface';
    if (duration < 5000) return 'engaged';
    return 'deep';
  }

  private assessTooltipEffectiveness(interaction: TooltipInteraction): number {
    const durationScore = Math.min(interaction.duration / 3000, 1);
    const depthScore = interaction.interactionDepth === 'deep' ? 1 : 
                     interaction.interactionDepth === 'engaged' ? 0.7 : 0.3;
    
    return Math.round((durationScore + depthScore) * 50);
  }

  private assessMemoryEfficiency(increase: number): string {
    const increaseMB = increase / 1024 / 1024;
    
    if (increaseMB < 5) return 'excellent';
    if (increaseMB < 15) return 'good';
    if (increaseMB < 30) return 'fair';
    return 'poor';
  }

  private calculatePositionScore(rect: any): number {
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    
    const elementCenterX = rect.x + rect.width / 2;
    const elementCenterY = rect.y + rect.height / 2;
    
    const distanceFromCenter = Math.sqrt(
      Math.pow(elementCenterX - centerX, 2) + Math.pow(elementCenterY - centerY, 2)
    );
    
    const maxDistance = Math.sqrt(Math.pow(centerX, 2) + Math.pow(centerY, 2));
    
    return Math.round((1 - distanceFromCenter / maxDistance) * 100);
  }

  private assessVisibilityOptimization(entry: IntersectionObserverEntry): string {
    if (entry.intersectionRatio >= 0.8) return 'optimal';
    if (entry.intersectionRatio >= 0.5) return 'good';
    if (entry.intersectionRatio >= 0.2) return 'partial';
    return 'poor';
  }

  private getLastUserAction(): string {
    // Simple heuristic - would be better to track this properly
    return 'unknown';
  }

  private assessRecoveryPossibility(errorType: string): boolean {
    const recoverableTypes = ['network_error', 'timeout', 'ui_error'];
    return recoverableTypes.includes(errorType);
  }

  private handleCustomMeasure(entry: PerformanceEntry): void {
    // Handle custom performance measures
    this.eventCallback({
      event_type: 'custom_performance_measure',
      event_category: 'performance',
      event_priority: 'low',
      event_data: {
        measure_name: entry.name,
        duration_ms: entry.duration,
        start_time: entry.startTime
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleNavigationTiming(entry: PerformanceNavigationTiming): void {
    this.eventCallback({
      event_type: 'navigation_performance',
      event_category: 'performance',
      event_priority: 'medium',
      event_data: {
        dom_content_loaded: entry.domContentLoadedEventEnd - entry.domContentLoadedEventStart,
        load_complete: entry.loadEventEnd - entry.loadEventStart,
        dns_lookup: entry.domainLookupEnd - entry.domainLookupStart,
        tcp_connect: entry.connectEnd - entry.connectStart,
        navigation_type: entry.type
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public destroy(): void {
    if (this.performanceObserver) {
      this.performanceObserver.disconnect();
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    
    this.renderTimings.clear();
    this.tooltipInteractions.clear();
    this.visualElements.clear();
  }
}