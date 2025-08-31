/**
 * Session Learning and User Progress Analytics Tracker
 * Monitors user learning curve, multi-tab usage, session recovery, and sophistication evolution
 */

import type { 
  LearningMetrics, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';
import { STORAGE_KEYS } from '@/shared/constants';

const logger = createLogger('LearningAnalyticsTracker');

interface SessionBreadcrumb {
  timestamp: number;
  action: string;
  context: Record<string, unknown>;
  url: string;
  userInitiated: boolean;
}

interface MultiTabState {
  tabId: string;
  url: string;
  isActive: boolean;
  lastActivity: number;
  sessionsCount: number;
  interactions: number;
}

interface LearningProgress {
  userId: string;
  sessionNumber: number;
  accuracyHistory: number[];
  speedHistory: number[]; // Time to first interaction
  confidenceHistory: number[];
  featureUsage: Map<string, number>;
  mistakePatterns: string[];
  learningVelocity: number;
  sophisticationLevel: 'beginner' | 'intermediate' | 'advanced';
}

interface IdleSession {
  startTime: number;
  endTime: number;
  duration: number;
  reason: 'user_away' | 'tab_hidden' | 'window_minimized' | 'system_idle';
  recoveryTime: number;
  dataLost: boolean;
}

export class LearningAnalyticsTracker {
  private breadcrumbs: SessionBreadcrumb[] = [];
  private multiTabStates: Map<string, MultiTabState> = new Map();
  private learningProgress: LearningProgress;
  private idleSessions: IdleSession[] = [];
  private activeTimeTracking = {
    sessionStart: Date.now(),
    totalActiveTime: 0,
    lastActivityTime: Date.now(),
    idleStartTime: 0,
    isIdle: false
  };

  private readonly maxBreadcrumbs = 100;
  private readonly idleThreshold = 30000; // 30 seconds
  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  // Cross-tab communication
  private broadcastChannel: BroadcastChannel | null = null;
  private tabId: string;

  constructor(
    userId: string,
    sessionId: string, 
    config: EnhancedMetricsConfig, 
    eventCallback: (event: UnifiedAnalyticsEvent) => void
  ) {
    this.config = config;
    this.eventCallback = eventCallback;
    this.tabId = `tab_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    
    this.learningProgress = this.loadLearningProgress(userId, sessionId);
    this.initializeMultiTabTracking();
    this.initializeBreadcrumbTracking();
    this.initializeIdleTracking();
    this.initializeLearningTracking();
  }

  private loadLearningProgress(userId: string, sessionId: string): LearningProgress {
    const stored = localStorage.getItem(`${STORAGE_KEYS.userId}_learning_progress`);
    
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as LearningProgress;
        parsed.sessionNumber++;
        return parsed;
      } catch (error) {
        logger.warn('Failed to parse stored learning progress:', error);
      }
    }

    return {
      userId,
      sessionNumber: 1,
      accuracyHistory: [],
      speedHistory: [],
      confidenceHistory: [],
      featureUsage: new Map(),
      mistakePatterns: [],
      learningVelocity: 0,
      sophisticationLevel: 'beginner'
    };
  }

  private saveLearningProgress(): void {
    try {
      const toStore = {
        ...this.learningProgress,
        featureUsage: Array.from(this.learningProgress.featureUsage.entries())
      };
      
      localStorage.setItem(
        `${STORAGE_KEYS.userId}_learning_progress`,
        JSON.stringify(toStore)
      );
    } catch (error) {
      logger.warn('Failed to save learning progress:', error);
    }
  }

  private initializeMultiTabTracking(): void {
    try {
      this.broadcastChannel = new BroadcastChannel('ai-slop-extension-tabs');
      
      // Register this tab
      this.multiTabStates.set(this.tabId, {
        tabId: this.tabId,
        url: window.location.href,
        isActive: true,
        lastActivity: Date.now(),
        sessionsCount: 1,
        interactions: 0
      });

      // Listen for messages from other tabs
      this.broadcastChannel.addEventListener('message', (event) => {
        this.handleTabCommunication(event.data);
      });

      // Announce this tab to others
      this.broadcastChannel.postMessage({
        type: 'tab_register',
        tabId: this.tabId,
        url: window.location.href,
        timestamp: Date.now()
      });

      // Handle tab visibility changes
      document.addEventListener('visibilitychange', () => {
        this.handleVisibilityChange();
      });

      // Handle beforeunload to clean up
      window.addEventListener('beforeunload', () => {
        this.handleTabClose();
      });

      // Periodic heartbeat to maintain tab registry
      setInterval(() => {
        this.sendTabHeartbeat();
      }, 10000); // Every 10 seconds

    } catch (error) {
      logger.warn('BroadcastChannel not supported, multi-tab tracking disabled:', error);
    }
  }

  private initializeBreadcrumbTracking(): void {
    // Track all user actions for session replay
    const trackAction = (action: string, context: Record<string, unknown> = {}, userInitiated = true) => {
      const breadcrumb: SessionBreadcrumb = {
        timestamp: Date.now(),
        action,
        context,
        url: window.location.href,
        userInitiated
      };

      this.breadcrumbs.push(breadcrumb);

      // Keep only recent breadcrumbs
      if (this.breadcrumbs.length > this.maxBreadcrumbs) {
        this.breadcrumbs.shift();
      }
    };

    // Track various user interactions
    document.addEventListener('click', (event) => {
      const target = event.target as Element;
      trackAction('click', {
        element: target.tagName.toLowerCase(),
        class: target.className,
        text: target.textContent?.slice(0, 100),
        coordinates: { x: event.clientX, y: event.clientY }
      });
    });

    document.addEventListener('keydown', (event) => {
      trackAction('keydown', {
        key: event.key,
        ctrlKey: event.ctrlKey,
        altKey: event.altKey,
        shiftKey: event.shiftKey
      });
    });

    // Track navigation events
    window.addEventListener('popstate', () => {
      trackAction('navigation', { 
        type: 'back_forward', 
        url: window.location.href 
      }, false);
    });

    // Track scroll events (throttled)
    let scrollTimeout: number | null = null;
    window.addEventListener('scroll', () => {
      if (scrollTimeout) return;
      
      scrollTimeout = window.setTimeout(() => {
        trackAction('scroll', {
          scrollY: window.scrollY,
          scrollPercent: Math.round((window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100)
        });
        scrollTimeout = null;
      }, 1000);
    }, { passive: true });
  }

  private initializeIdleTracking(): void {
    const updateActivity = () => {
      const now = Date.now();
      
      if (this.activeTimeTracking.isIdle) {
        // User came back from idle
        const idleDuration = now - this.activeTimeTracking.idleStartTime;
        
        const idleSession: IdleSession = {
          startTime: this.activeTimeTracking.idleStartTime,
          endTime: now,
          duration: idleDuration,
          reason: this.determineIdleReason(),
          recoveryTime: 0, // Will be updated if recovery is needed
          dataLost: false
        };

        this.idleSessions.push(idleSession);
        this.trackSessionRecovery(idleSession);
        
        this.activeTimeTracking.isIdle = false;
      }

      this.activeTimeTracking.lastActivityTime = now;
    };

    const checkIdle = () => {
      const now = Date.now();
      const timeSinceActivity = now - this.activeTimeTracking.lastActivityTime;

      if (!this.activeTimeTracking.isIdle && timeSinceActivity > this.idleThreshold) {
        this.activeTimeTracking.isIdle = true;
        this.activeTimeTracking.idleStartTime = now;
        
        this.eventCallback({
          event_type: 'idle_session_start',
          event_category: 'learning',
          event_priority: 'low',
          event_data: {
            idle_threshold_ms: this.idleThreshold,
            time_since_activity_ms: timeSinceActivity,
            active_time_before_idle_ms: this.activeTimeTracking.totalActiveTime
          },
          client_timestamp: new Date().toISOString()
        });
      }

      // Update total active time
      if (!this.activeTimeTracking.isIdle) {
        this.activeTimeTracking.totalActiveTime = now - this.activeTimeTracking.sessionStart;
      }
    };

    // Activity event listeners
    ['click', 'keydown', 'mousemove', 'scroll'].forEach(event => {
      document.addEventListener(event, updateActivity, { passive: true });
    });

    // Check idle state every 5 seconds
    setInterval(checkIdle, 5000);
  }

  private initializeLearningTracking(): void {
    // Track feature discovery and usage
    const trackFeatureUsage = (feature: string) => {
      const currentUsage = this.learningProgress.featureUsage.get(feature) || 0;
      this.learningProgress.featureUsage.set(feature, currentUsage + 1);
      
      // Check if this is first time using this feature
      if (currentUsage === 0) {
        this.eventCallback({
          event_type: 'feature_discovery',
          event_category: 'learning',
          event_priority: 'medium',
          event_data: {
            feature_name: feature,
            session_number: this.learningProgress.sessionNumber,
            discovery_order: this.learningProgress.featureUsage.size,
            time_to_discovery: Date.now() - this.activeTimeTracking.sessionStart
          },
          client_timestamp: new Date().toISOString()
        });
      }
    };

    // Track AI detection interactions
    document.addEventListener('click', (event) => {
      const target = event.target as Element;
      
      if (target.closest('.ai-detection-icon')) {
        trackFeatureUsage('ai_detection_icon');
        this.trackInteractionSpeed();
      } else if (target.closest('.chat-window')) {
        trackFeatureUsage('chat_interface');
      } else if (target.closest('.tooltip')) {
        trackFeatureUsage('tooltip_system');
      }
    });

    // Periodic sophistication assessment
    setInterval(() => {
      this.assessUserSophistication();
    }, 60000); // Every minute
  }

  public trackInteractionAccuracy(correct: boolean, confidence: number): void {
    this.learningProgress.accuracyHistory.push(correct ? 1 : 0);
    this.learningProgress.confidenceHistory.push(confidence);
    
    // Keep only recent history (last 50 interactions)
    if (this.learningProgress.accuracyHistory.length > 50) {
      this.learningProgress.accuracyHistory.shift();
      this.learningProgress.confidenceHistory.shift();
    }

    const currentAccuracy = this.calculateCurrentAccuracy();
    const accuracyImprovement = this.calculateAccuracyImprovement();
    
    this.eventCallback({
      event_type: 'learning_accuracy_update',
      event_category: 'learning',
      event_priority: 'medium',
      event_data: {
        current_accuracy: currentAccuracy,
        accuracy_improvement: accuracyImprovement,
        confidence_level: confidence,
        interaction_count: this.learningProgress.accuracyHistory.length,
        learning_trend: this.analyzeLearningTrend(),
        mistake_pattern: !correct ? this.identifyMistakePattern() : null
      },
      client_timestamp: new Date().toISOString()
    });

    this.saveLearningProgress();
  }

  private trackInteractionSpeed(): void {
    const interactionTime = Date.now() - this.activeTimeTracking.lastActivityTime;
    this.learningProgress.speedHistory.push(interactionTime);
    
    if (this.learningProgress.speedHistory.length > 30) {
      this.learningProgress.speedHistory.shift();
    }

    const speedImprovement = this.calculateSpeedImprovement();
    
    this.eventCallback({
      event_type: 'interaction_speed_tracking',
      event_category: 'learning',
      event_priority: 'low',
      event_data: {
        interaction_time_ms: interactionTime,
        speed_improvement: speedImprovement,
        average_speed: this.calculateAverageSpeed(),
        speed_trend: this.analyzeSpeedTrend()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleTabCommunication(data: any): void {
    switch (data.type) {
      case 'tab_register':
        this.multiTabStates.set(data.tabId, {
          tabId: data.tabId,
          url: data.url,
          isActive: true,
          lastActivity: data.timestamp,
          sessionsCount: 1,
          interactions: 0
        });
        this.trackMultiTabUsage();
        break;
        
      case 'tab_heartbeat':
        const existingTab = this.multiTabStates.get(data.tabId);
        if (existingTab) {
          existingTab.lastActivity = data.timestamp;
          existingTab.isActive = data.isActive;
          existingTab.interactions = data.interactions;
        }
        break;
        
      case 'tab_close':
        this.multiTabStates.delete(data.tabId);
        this.trackMultiTabUsage();
        break;
    }
  }

  private handleVisibilityChange(): void {
    const isHidden = document.hidden;
    const tabState = this.multiTabStates.get(this.tabId);
    
    if (tabState) {
      tabState.isActive = !isHidden;
      tabState.lastActivity = Date.now();
    }

    this.eventCallback({
      event_type: 'tab_visibility_change',
      event_category: 'learning',
      event_priority: 'low',
      event_data: {
        is_hidden: isHidden,
        tab_id: this.tabId,
        active_tabs_count: this.getActiveTabsCount(),
        session_duration_ms: Date.now() - this.activeTimeTracking.sessionStart
      },
      client_timestamp: new Date().toISOString()
    });

    // Broadcast to other tabs
    this.broadcastChannel?.postMessage({
      type: 'tab_heartbeat',
      tabId: this.tabId,
      isActive: !isHidden,
      interactions: tabState?.interactions || 0,
      timestamp: Date.now()
    });
  }

  private handleTabClose(): void {
    this.broadcastChannel?.postMessage({
      type: 'tab_close',
      tabId: this.tabId,
      timestamp: Date.now()
    });
    
    this.eventCallback({
      event_type: 'tab_session_end',
      event_category: 'learning',
      event_priority: 'medium',
      event_data: {
        tab_id: this.tabId,
        session_duration_ms: Date.now() - this.activeTimeTracking.sessionStart,
        total_interactions: this.multiTabStates.get(this.tabId)?.interactions || 0,
        breadcrumb_count: this.breadcrumbs.length,
        final_url: window.location.href
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private sendTabHeartbeat(): void {
    const tabState = this.multiTabStates.get(this.tabId);
    if (!tabState) return;

    this.broadcastChannel?.postMessage({
      type: 'tab_heartbeat',
      tabId: this.tabId,
      isActive: !document.hidden,
      interactions: tabState.interactions,
      timestamp: Date.now()
    });
  }

  private trackMultiTabUsage(): void {
    const activeTabs = this.getActiveTabsCount();
    const totalTabs = this.multiTabStates.size;
    
    this.eventCallback({
      event_type: 'multi_tab_usage',
      event_category: 'learning',
      event_priority: 'medium',
      event_data: {
        total_tabs: totalTabs,
        active_tabs: activeTabs,
        tab_efficiency: activeTabs > 0 ? 1 / activeTabs : 0,
        usage_pattern: this.classifyTabUsagePattern(totalTabs, activeTabs),
        tab_switching_frequency: this.calculateTabSwitchingFrequency()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private trackSessionRecovery(idleSession: IdleSession): void {
    const recoveryStart = Date.now();
    
    // Monitor for recovery actions
    const recoveryTracker = () => {
      const recoveryTime = Date.now() - recoveryStart;
      
      this.eventCallback({
        event_type: 'session_recovery',
        event_category: 'learning',
        event_priority: 'medium',
        event_data: {
          idle_duration_ms: idleSession.duration,
          idle_reason: idleSession.reason,
          recovery_time_ms: recoveryTime,
          recovery_successful: true,
          data_preserved: !idleSession.dataLost,
          session_continuity_score: this.calculateSessionContinuity(idleSession)
        },
        client_timestamp: new Date().toISOString()
      });
      
      // Remove listener after tracking
      document.removeEventListener('click', recoveryTracker);
    };

    document.addEventListener('click', recoveryTracker, { once: true });
  }

  private assessUserSophistication(): void {
    const metrics = this.calculateSophisticationMetrics();
    const previousLevel = this.learningProgress.sophisticationLevel;
    const newLevel = this.determineSophisticationLevel(metrics);
    
    if (newLevel !== previousLevel) {
      this.learningProgress.sophisticationLevel = newLevel;
      
      this.eventCallback({
        event_type: 'sophistication_level_change',
        event_category: 'learning',
        event_priority: 'high',
        event_data: {
          previous_level: previousLevel,
          new_level: newLevel,
          session_number: this.learningProgress.sessionNumber,
          metrics: metrics,
          progression_time_ms: Date.now() - this.activeTimeTracking.sessionStart
        },
        client_timestamp: new Date().toISOString()
      });
    }

    // Regular sophistication tracking
    this.eventCallback({
      event_type: 'user_sophistication_assessment',
      event_category: 'learning',
      event_priority: 'low',
      event_data: {
        current_level: newLevel,
        sophistication_score: metrics.overallScore,
        feature_mastery_count: metrics.featureMasteryCount,
        accuracy_trend: metrics.accuracyTrend,
        speed_proficiency: metrics.speedProficiency,
        learning_velocity: this.learningProgress.learningVelocity
      },
      client_timestamp: new Date().toISOString()
    });

    this.saveLearningProgress();
  }

  public trackCrossSessionLearning(): void {
    const sessionMetrics = this.calculateSessionMetrics();
    
    this.eventCallback({
      event_type: 'cross_session_learning',
      event_category: 'learning',
      event_priority: 'medium',
      event_data: {
        session_number: this.learningProgress.sessionNumber,
        retention_rate: sessionMetrics.retentionRate,
        skill_transfer: sessionMetrics.skillTransfer,
        knowledge_persistence: sessionMetrics.knowledgePersistence,
        cumulative_improvement: sessionMetrics.cumulativeImprovement,
        learning_plateau_indicator: sessionMetrics.plateauIndicator
      },
      client_timestamp: new Date().toISOString()
    });
  }

  // Helper methods
  private calculateCurrentAccuracy(): number {
    if (this.learningProgress.accuracyHistory.length === 0) return 0;
    
    const recentHistory = this.learningProgress.accuracyHistory.slice(-10);
    return recentHistory.reduce((sum, acc) => sum + acc, 0) / recentHistory.length;
  }

  private calculateAccuracyImprovement(): number {
    if (this.learningProgress.accuracyHistory.length < 10) return 0;
    
    const early = this.learningProgress.accuracyHistory.slice(0, 5);
    const recent = this.learningProgress.accuracyHistory.slice(-5);
    
    const earlyAvg = early.reduce((a, b) => a + b, 0) / early.length;
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    
    return recentAvg - earlyAvg;
  }

  private calculateSpeedImprovement(): number {
    if (this.learningProgress.speedHistory.length < 10) return 0;
    
    const early = this.learningProgress.speedHistory.slice(0, 5);
    const recent = this.learningProgress.speedHistory.slice(-5);
    
    const earlyAvg = early.reduce((a, b) => a + b, 0) / early.length;
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    
    // Lower times are better, so improvement is negative change
    return (earlyAvg - recentAvg) / earlyAvg;
  }

  private calculateAverageSpeed(): number {
    if (this.learningProgress.speedHistory.length === 0) return 0;
    
    return this.learningProgress.speedHistory.reduce((a, b) => a + b, 0) / 
           this.learningProgress.speedHistory.length;
  }

  private analyzeLearningTrend(): string {
    const improvement = this.calculateAccuracyImprovement();
    
    if (improvement > 0.1) return 'improving';
    if (improvement < -0.1) return 'declining';
    return 'stable';
  }

  private analyzeSpeedTrend(): string {
    const improvement = this.calculateSpeedImprovement();
    
    if (improvement > 0.1) return 'getting_faster';
    if (improvement < -0.1) return 'getting_slower';
    return 'stable';
  }

  private identifyMistakePattern(): string {
    // Simple pattern identification - could be enhanced with ML
    const recentMistakes = this.learningProgress.mistakePatterns.slice(-5);
    const patternCounts = new Map<string, number>();
    
    recentMistakes.forEach(pattern => {
      patternCounts.set(pattern, (patternCounts.get(pattern) || 0) + 1);
    });
    
    let mostCommonPattern = 'unknown';
    let maxCount = 0;
    
    patternCounts.forEach((count, pattern) => {
      if (count > maxCount) {
        maxCount = count;
        mostCommonPattern = pattern;
      }
    });
    
    return mostCommonPattern;
  }

  private getActiveTabsCount(): number {
    return Array.from(this.multiTabStates.values()).filter(tab => tab.isActive).length;
  }

  private classifyTabUsagePattern(total: number, active: number): string {
    if (total === 1) return 'single_tab';
    if (active === 1 && total > 1) return 'focused_multi_tab';
    if (active === total) return 'all_active';
    if (active > total / 2) return 'mostly_active';
    return 'scattered_usage';
  }

  private calculateTabSwitchingFrequency(): number {
    // Simple heuristic based on visibility changes
    const visibilityChanges = this.breadcrumbs.filter(b => b.action === 'tab_visibility_change').length;
    const sessionDuration = Date.now() - this.activeTimeTracking.sessionStart;
    
    return visibilityChanges / (sessionDuration / 60000); // Changes per minute
  }

  private determineIdleReason(): IdleSession['reason'] {
    if (document.hidden) return 'tab_hidden';
    // Could add more sophisticated detection
    return 'user_away';
  }

  private calculateSessionContinuity(idleSession: IdleSession): number {
    const continuityFactors = {
      shortIdle: idleSession.duration < 60000 ? 0.9 : 0.5,
      dataPreserved: !idleSession.dataLost ? 0.9 : 0.3,
      quickRecovery: idleSession.recoveryTime < 5000 ? 0.9 : 0.6
    };
    
    return (continuityFactors.shortIdle + continuityFactors.dataPreserved + continuityFactors.quickRecovery) / 3;
  }

  private calculateSophisticationMetrics(): {
    overallScore: number;
    featureMasteryCount: number;
    accuracyTrend: number;
    speedProficiency: number;
  } {
    const featureMasteryCount = Array.from(this.learningProgress.featureUsage.values())
      .filter(usage => usage >= 5).length; // Mastery threshold
    
    const accuracyTrend = this.analyzeLearningTrend() === 'improving' ? 1 : 
                         this.analyzeLearningTrend() === 'declining' ? -1 : 0;
    
    const speedProficiency = this.calculateSpeedImprovement();
    
    const overallScore = (featureMasteryCount / 10) + // Max 10 features
                        (this.calculateCurrentAccuracy()) +
                        (speedProficiency > 0 ? 0.5 : 0) +
                        (accuracyTrend > 0 ? 0.5 : 0);
    
    return {
      overallScore: Math.min(overallScore, 3),
      featureMasteryCount,
      accuracyTrend,
      speedProficiency
    };
  }

  private determineSophisticationLevel(metrics: any): 'beginner' | 'intermediate' | 'advanced' {
    if (metrics.overallScore >= 2.5) return 'advanced';
    if (metrics.overallScore >= 1.5) return 'intermediate';
    return 'beginner';
  }

  private calculateSessionMetrics(): {
    retentionRate: number;
    skillTransfer: number;
    knowledgePersistence: number;
    cumulativeImprovement: number;
    plateauIndicator: number;
  } {
    // Placeholder calculations - would need more sophisticated analysis
    return {
      retentionRate: this.calculateCurrentAccuracy(),
      skillTransfer: Math.min(this.learningProgress.featureUsage.size / 10, 1),
      knowledgePersistence: this.learningProgress.sessionNumber > 1 ? 0.8 : 0.5,
      cumulativeImprovement: this.calculateAccuracyImprovement(),
      plateauIndicator: Math.abs(this.calculateAccuracyImprovement()) < 0.05 ? 1 : 0
    };
  }

  public getBreadcrumbTrail(): SessionBreadcrumb[] {
    return [...this.breadcrumbs];
  }

  public getLearningMetrics(): LearningMetrics {
    return {
      sessionNumber: this.learningProgress.sessionNumber,
      accuracyImprovement: this.calculateAccuracyImprovement(),
      speedImprovement: this.calculateSpeedImprovement(),
      confidenceGrowth: this.calculateConfidenceGrowth(),
      featureDiscoveryRate: this.calculateFeatureDiscoveryRate(),
      sophisticationLevel: this.learningProgress.sophisticationLevel
    };
  }

  private calculateConfidenceGrowth(): number {
    if (this.learningProgress.confidenceHistory.length < 10) return 0;
    
    const early = this.learningProgress.confidenceHistory.slice(0, 5);
    const recent = this.learningProgress.confidenceHistory.slice(-5);
    
    const earlyAvg = early.reduce((a, b) => a + b, 0) / early.length;
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    
    return recentAvg - earlyAvg;
  }

  private calculateFeatureDiscoveryRate(): number {
    const sessionDuration = Date.now() - this.activeTimeTracking.sessionStart;
    return this.learningProgress.featureUsage.size / (sessionDuration / 60000); // Features per minute
  }

  public destroy(): void {
    this.saveLearningProgress();
    
    if (this.broadcastChannel) {
      this.broadcastChannel.close();
    }
    
    this.breadcrumbs = [];
    this.multiTabStates.clear();
    this.idleSessions = [];
  }
}