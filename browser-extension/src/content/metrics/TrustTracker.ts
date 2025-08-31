/**
 * Trust and Detection Analytics Tracker
 * Monitors user trust calibration, detection feedback, and confidence interactions
 */

import type { 
  TrustScore, 
  DetectionFeedback, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';
import { STORAGE_KEYS } from '@/shared/constants';

const logger = createLogger('TrustTracker');

interface DetectionInteraction {
  postId: string;
  confidence: number;
  detectionResult: 'ai' | 'human' | 'uncertain';
  timestamp: number;
  userAction: string;
  responseTime: number;
}

interface TrustEvolution {
  userId: string;
  sessionId: string;
  initialScore: number;
  currentScore: number;
  interactions: DetectionInteraction[];
  feedbackHistory: DetectionFeedback[];
  fatigueScore: number;
  lastUpdate: number;
}

export class TrustTracker {
  private trustEvolution: TrustEvolution;
  private detectionHistory: Map<string, DetectionInteraction> = new Map();
  private interactionTimes: Map<string, number> = new Map();
  private fatigueMetrics = {
    consecutiveIgnores: 0,
    decreasingEngagement: 0,
    lastEngagementTime: Date.now(),
    sessionInteractionCount: 0
  };

  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  constructor(
    userId: string,
    sessionId: string,
    config: EnhancedMetricsConfig,
    eventCallback: (event: UnifiedAnalyticsEvent) => void
  ) {
    this.config = config;
    this.eventCallback = eventCallback;
    
    this.trustEvolution = this.loadTrustEvolution(userId, sessionId);
    this.initializeTrustTracking();
  }

  private loadTrustEvolution(userId: string, sessionId: string): TrustEvolution {
    const stored = localStorage.getItem(`${STORAGE_KEYS.userId}_trust_evolution`);
    
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as TrustEvolution;
        parsed.sessionId = sessionId; // Update session
        return parsed;
      } catch (error) {
        logger.warn('Failed to parse stored trust evolution:', error);
      }
    }

    // Initialize new trust evolution
    return {
      userId,
      sessionId,
      initialScore: 0.5, // Neutral starting point
      currentScore: 0.5,
      interactions: [],
      feedbackHistory: [],
      fatigueScore: 0,
      lastUpdate: Date.now()
    };
  }

  private saveTrustEvolution(): void {
    try {
      localStorage.setItem(
        `${STORAGE_KEYS.userId}_trust_evolution`,
        JSON.stringify(this.trustEvolution)
      );
    } catch (error) {
      logger.warn('Failed to save trust evolution:', error);
    }
  }

  private initializeTrustTracking(): void {
    // Track clicks on AI detection icons
    document.addEventListener('click', (event) => {
      const target = event.target as Element;
      if (this.isDetectionIcon(target)) {
        this.trackDetectionIconClick(target, event);
      }
    });

    // Track hover behavior on detection results
    document.addEventListener('mouseover', (event) => {
      const target = event.target as Element;
      if (this.isDetectionIcon(target)) {
        this.trackDetectionIconHover(target, true);
      }
    });

    document.addEventListener('mouseout', (event) => {
      const target = event.target as Element;
      if (this.isDetectionIcon(target)) {
        this.trackDetectionIconHover(target, false);
      }
    });

    // Track user feedback through UI interactions
    this.setupFeedbackTracking();
  }

  public trackDetectionResult(
    postId: string, 
    result: 'ai' | 'human' | 'uncertain', 
    confidence: number,
    metadata: Record<string, unknown> = {}
  ): void {
    const now = Date.now();
    
    const interaction: DetectionInteraction = {
      postId,
      confidence,
      detectionResult: result,
      timestamp: now,
      userAction: 'detected',
      responseTime: 0
    };

    this.detectionHistory.set(postId, interaction);
    this.interactionTimes.set(postId, now);
    
    this.eventCallback({
      event_type: 'detection_confidence_interaction',
      event_category: 'trust',
      event_priority: 'high',
      post_id: postId,
      event_data: {
        detection_result: result,
        confidence_level: confidence,
        confidence_category: this.categorizeConfidence(confidence),
        trust_score_before: this.trustEvolution.currentScore,
        session_detection_count: this.detectionHistory.size,
        ...metadata
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private trackDetectionIconClick(target: Element, event: MouseEvent): void {
    const postId = this.getPostId(target);
    if (!postId) return;

    const detection = this.detectionHistory.get(postId);
    if (!detection) return;

    const now = Date.now();
    const responseTime = now - this.interactionTimes.get(postId)!;
    
    detection.userAction = 'clicked';
    detection.responseTime = responseTime;
    
    this.fatigueMetrics.sessionInteractionCount++;
    this.fatigueMetrics.lastEngagementTime = now;
    this.fatigueMetrics.consecutiveIgnores = 0; // Reset ignore counter
    
    // Calculate engagement quality based on response time
    const engagementQuality = this.assessEngagementQuality(responseTime, detection.confidence);
    
    // Update trust score based on interaction
    this.updateTrustScore(detection, 'positive_engagement');
    
    this.eventCallback({
      event_type: 'detection_icon_interaction',
      event_category: 'trust',
      event_priority: 'high',
      post_id: postId,
      event_data: {
        interaction_type: 'click',
        response_time_ms: responseTime,
        confidence_level: detection.confidence,
        detection_result: detection.detectionResult,
        engagement_quality: engagementQuality,
        trust_score_after: this.trustEvolution.currentScore,
        session_interaction_count: this.fatigueMetrics.sessionInteractionCount,
        is_quick_response: responseTime < 2000
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private trackDetectionIconHover(target: Element, isEntering: boolean): void {
    const postId = this.getPostId(target);
    if (!postId) return;

    if (isEntering) {
      this.interactionTimes.set(`${postId}_hover`, Date.now());
    } else {
      const hoverStart = this.interactionTimes.get(`${postId}_hover`);
      if (hoverStart) {
        const hoverDuration = Date.now() - hoverStart;
        const detection = this.detectionHistory.get(postId);
        
        if (hoverDuration > 500) { // Meaningful hover
          this.eventCallback({
            event_type: 'detection_icon_hover',
            event_category: 'trust',
            event_priority: 'medium',
            post_id: postId,
            event_data: {
              hover_duration_ms: hoverDuration,
              confidence_level: detection?.confidence || 0,
              detection_result: detection?.detectionResult || 'unknown',
              hover_quality: this.assessHoverQuality(hoverDuration),
              trust_indication: hoverDuration > 2000 ? 'skeptical' : 'curious'
            },
            client_timestamp: new Date().toISOString()
          });
        }
        
        this.interactionTimes.delete(`${postId}_hover`);
      }
    }
  }

  public trackUserFeedback(
    postId: string,
    userFeedback: 'correct' | 'incorrect' | 'uncertain',
    feedbackMethod: 'button' | 'implicit' | 'chat' = 'implicit'
  ): void {
    const detection = this.detectionHistory.get(postId);
    if (!detection) return;

    const feedback: DetectionFeedback = {
      postId,
      detectionResult: detection.detectionResult,
      userFeedback,
      confidence: detection.confidence,
      feedbackTime: Date.now()
    };

    this.trustEvolution.feedbackHistory.push(feedback);
    
    // Update trust score based on feedback
    const isCorrectFeedback = userFeedback === 'correct';
    this.updateTrustScore(detection, isCorrectFeedback ? 'positive_feedback' : 'negative_feedback');
    
    // Check for potential false positive pattern
    if (userFeedback === 'incorrect') {
      this.analyzeForFalsePositivePattern(feedback);
    }

    this.eventCallback({
      event_type: 'false_positive_report',
      event_category: 'trust',
      event_priority: 'high',
      post_id: postId,
      event_data: {
        user_feedback: userFeedback,
        detection_was: detection.detectionResult,
        confidence_level: detection.confidence,
        feedback_method: feedbackMethod,
        trust_score_change: this.calculateTrustScoreChange(),
        response_time_ms: detection.responseTime,
        is_potential_false_positive: userFeedback === 'incorrect' && detection.detectionResult === 'ai',
        feedback_reliability: this.assessFeedbackReliability(userFeedback)
      },
      client_timestamp: new Date().toISOString()
    });

    this.saveTrustEvolution();
  }

  public trackDetectionFatigue(): void {
    const now = Date.now();
    const timeSinceLastInteraction = now - this.fatigueMetrics.lastEngagementTime;
    
    // Check for signs of fatigue
    if (timeSinceLastInteraction > 30000) { // 30 seconds of no interaction
      this.fatigueMetrics.consecutiveIgnores++;
    }

    // Calculate fatigue score
    const newFatigueScore = this.calculateFatigueScore();
    const fatigueIncrease = newFatigueScore - this.trustEvolution.fatigueScore;
    
    this.trustEvolution.fatigueScore = newFatigueScore;

    if (fatigueIncrease > 0.1) { // Significant fatigue increase
      this.eventCallback({
        event_type: 'detection_fatigue',
        event_category: 'trust',
        event_priority: 'medium',
        event_data: {
          fatigue_score: newFatigueScore,
          fatigue_level: this.categorizeFatigueLevel(newFatigueScore),
          consecutive_ignores: this.fatigueMetrics.consecutiveIgnores,
          time_since_last_interaction_ms: timeSinceLastInteraction,
          session_interaction_count: this.fatigueMetrics.sessionInteractionCount,
          declining_engagement: this.fatigueMetrics.decreasingEngagement,
          recommendations: this.generateFatigueRecommendations(newFatigueScore)
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  public trackComparativeBehavior(postId: string, isAIContent: boolean): void {
    const behavior = this.analyzeBehaviorDifferences(postId, isAIContent);
    
    this.eventCallback({
      event_type: 'ai_vs_human_behavior',
      event_category: 'trust',
      event_priority: 'medium',
      post_id: postId,
      event_data: {
        content_type: isAIContent ? 'ai' : 'human',
        engagement_pattern: behavior.engagementPattern,
        interaction_speed: behavior.interactionSpeed,
        attention_duration: behavior.attentionDuration,
        skepticism_level: behavior.skepticismLevel,
        trust_bias: behavior.trustBias,
        behavioral_consistency: behavior.consistency
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private setupFeedbackTracking(): void {
    // Track implicit feedback through UI interactions
    document.addEventListener('click', (event) => {
      const target = event.target as Element;
      
      // Track "report" or "feedback" button clicks
      if (target.classList.contains('report-button') || 
          target.classList.contains('feedback-button')) {
        const postId = this.getPostId(target);
        if (postId) {
          // Infer feedback type from button context
          const feedbackType = this.inferFeedbackType(target);
          this.trackUserFeedback(postId, feedbackType, 'button');
        }
      }
    });
  }

  private updateTrustScore(interaction: DetectionInteraction, eventType: string): void {
    const previousScore = this.trustEvolution.currentScore;
    
    let scoreChange = 0;
    switch (eventType) {
      case 'positive_engagement':
        scoreChange = 0.02 * interaction.confidence;
        break;
      case 'positive_feedback':
        scoreChange = 0.05 * interaction.confidence;
        break;
      case 'negative_feedback':
        scoreChange = -0.03 * interaction.confidence;
        break;
      default:
        scoreChange = 0;
    }

    // Apply fatigue penalty
    const fatiguePenalty = this.trustEvolution.fatigueScore * 0.1;
    scoreChange *= (1 - fatiguePenalty);

    // Update score with bounds
    this.trustEvolution.currentScore = Math.max(0, Math.min(1, previousScore + scoreChange));
    this.trustEvolution.lastUpdate = Date.now();

    // Track significant trust changes
    if (Math.abs(scoreChange) > 0.05) {
      this.eventCallback({
        event_type: 'trust_score_change',
        event_category: 'trust',
        event_priority: 'high',
        event_data: {
          previous_score: previousScore,
          new_score: this.trustEvolution.currentScore,
          score_change: scoreChange,
          change_reason: eventType,
          confidence_factor: interaction.confidence,
          fatigue_penalty: fatiguePenalty,
          total_interactions: this.trustEvolution.interactions.length
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private calculateFatigueScore(): number {
    const factors = {
      consecutiveIgnores: Math.min(this.fatigueMetrics.consecutiveIgnores / 10, 1),
      timeFactor: Math.min((Date.now() - this.fatigueMetrics.lastEngagementTime) / 300000, 1), // 5 min max
      interactionDensity: Math.max(0, 1 - (this.fatigueMetrics.sessionInteractionCount / 20)),
      decreasingEngagement: this.fatigueMetrics.decreasingEngagement / 10
    };

    return Math.min(
      (factors.consecutiveIgnores * 0.4 + 
       factors.timeFactor * 0.3 + 
       factors.interactionDensity * 0.2 + 
       factors.decreasingEngagement * 0.1),
      1
    );
  }

  // Helper methods
  private isDetectionIcon(element: Element): boolean {
    return element.classList.contains('ai-detection-icon') ||
           element.closest('.ai-detection-icon') !== null;
  }

  private getPostId(element: Element): string | null {
    return element.closest('[data-post-id]')?.getAttribute('data-post-id') || null;
  }

  private categorizeConfidence(confidence: number): string {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.6) return 'medium';
    if (confidence >= 0.4) return 'low';
    return 'very_low';
  }

  private assessEngagementQuality(responseTime: number, confidence: number): string {
    if (responseTime < 500) return 'impulsive';
    if (responseTime < 2000 && confidence > 0.7) return 'confident';
    if (responseTime > 5000) return 'deliberative';
    return 'normal';
  }

  private assessHoverQuality(duration: number): string {
    if (duration < 1000) return 'brief';
    if (duration < 3000) return 'curious';
    if (duration > 5000) return 'skeptical';
    return 'interested';
  }

  private analyzeForFalsePositivePattern(feedback: DetectionFeedback): void {
    const recentIncorrect = this.trustEvolution.feedbackHistory
      .filter(f => f.feedbackTime > Date.now() - 300000) // Last 5 minutes
      .filter(f => f.userFeedback === 'incorrect').length;

    if (recentIncorrect >= 3) {
      this.eventCallback({
        event_type: 'false_positive_pattern_detected',
        event_category: 'trust',
        event_priority: 'critical',
        event_data: {
          recent_incorrect_count: recentIncorrect,
          pattern_confidence: recentIncorrect / 5,
          time_window_minutes: 5,
          requires_model_adjustment: true
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  private calculateTrustScoreChange(): number {
    if (this.trustEvolution.interactions.length < 2) return 0;
    
    const recent = this.trustEvolution.interactions.slice(-2);
    return this.trustEvolution.currentScore - (recent[0] as any).trustScore || 0;
  }

  private assessFeedbackReliability(feedback: string): number {
    // Simple heuristic based on user's historical accuracy
    const totalFeedback = this.trustEvolution.feedbackHistory.length;
    if (totalFeedback < 5) return 0.5; // Neutral for new users
    
    const consistentFeedback = this.trustEvolution.feedbackHistory
      .filter(f => f.userFeedback === feedback).length;
    
    return Math.min(consistentFeedback / totalFeedback, 1);
  }

  private categorizeFatigueLevel(score: number): string {
    if (score >= 0.8) return 'high';
    if (score >= 0.5) return 'medium';
    if (score >= 0.2) return 'low';
    return 'none';
  }

  private generateFatigueRecommendations(score: number): string[] {
    const recommendations = [];
    
    if (score > 0.6) {
      recommendations.push('reduce_notification_frequency');
      recommendations.push('improve_detection_accuracy');
    }
    if (score > 0.4) {
      recommendations.push('add_gamification_elements');
    }
    
    return recommendations;
  }

  private analyzeBehaviorDifferences(postId: string, isAI: boolean): any {
    // Placeholder for behavioral analysis
    return {
      engagementPattern: 'normal',
      interactionSpeed: 'medium',
      attentionDuration: 2000,
      skepticismLevel: isAI ? 'high' : 'low',
      trustBias: this.trustEvolution.currentScore > 0.7 ? 'positive' : 'negative',
      consistency: 0.8
    };
  }

  private inferFeedbackType(element: Element): 'correct' | 'incorrect' | 'uncertain' {
    const text = element.textContent?.toLowerCase() || '';
    if (text.includes('wrong') || text.includes('incorrect')) return 'incorrect';
    if (text.includes('right') || text.includes('correct')) return 'correct';
    return 'uncertain';
  }

  public getTrustScore(): TrustScore {
    return {
      currentScore: this.trustEvolution.currentScore,
      previousScore: this.trustEvolution.initialScore,
      factors: {
        accuracy: this.calculateAccuracyFactor(),
        consistency: this.calculateConsistencyFactor(),
        userFeedback: this.calculateFeedbackFactor(),
        timeUsed: this.calculateTimeUsedFactor()
      },
      lastUpdated: this.trustEvolution.lastUpdate
    };
  }

  private calculateAccuracyFactor(): number {
    if (this.trustEvolution.feedbackHistory.length === 0) return 0.5;
    
    const correct = this.trustEvolution.feedbackHistory
      .filter(f => f.userFeedback === 'correct').length;
    
    return correct / this.trustEvolution.feedbackHistory.length;
  }

  private calculateConsistencyFactor(): number {
    // Measure consistency in user behavior
    return Math.min(this.trustEvolution.interactions.length / 10, 1);
  }

  private calculateFeedbackFactor(): number {
    return Math.min(this.trustEvolution.feedbackHistory.length / 20, 1);
  }

  private calculateTimeUsedFactor(): number {
    const sessionDuration = Date.now() - this.trustEvolution.lastUpdate;
    return Math.min(sessionDuration / 1800000, 1); // 30 minutes max
  }

  public destroy(): void {
    this.saveTrustEvolution();
    this.detectionHistory.clear();
    this.interactionTimes.clear();
  }
}