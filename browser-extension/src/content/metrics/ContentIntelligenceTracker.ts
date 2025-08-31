/**
 * Content Intelligence and Analysis Tracker
 * Analyzes post characteristics, network effects, temporal patterns, and content clustering
 */

import type { 
  ContentCharacteristics, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';

const logger = createLogger('ContentIntelligenceTracker');

interface ContentVelocity {
  postsPerMinute: number;
  averageTimeBetweenPosts: number;
  burstPatterns: number[];
  contentDensity: number;
}

interface NetworkEffect {
  authorType: 'friend' | 'page' | 'group' | 'sponsored' | 'unknown';
  authorId: string;
  connectionStrength: number;
  influenceScore: number;
  contentPattern: string;
}

interface TemporalPattern {
  timeOfDay: number; // 0-23
  dayOfWeek: number; // 0-6
  seasonality: 'morning' | 'afternoon' | 'evening' | 'night';
  userActivityLevel: 'low' | 'medium' | 'high';
  contentFlowRate: number;
}

interface ContentCluster {
  clusterId: string;
  theme: string;
  postIds: string[];
  similarity: number;
  characteristics: ContentCharacteristics[];
  detectionPattern: 'consistent' | 'mixed' | 'anomalous';
}

export class ContentIntelligenceTracker {
  private postCharacteristics: Map<string, ContentCharacteristics> = new Map();
  private contentVelocity: ContentVelocity = {
    postsPerMinute: 0,
    averageTimeBetweenPosts: 0,
    burstPatterns: [],
    contentDensity: 0
  };
  private networkEffects: Map<string, NetworkEffect> = new Map();
  private temporalPatterns: TemporalPattern[] = [];
  private contentClusters: Map<string, ContentCluster> = new Map();
  
  private postTimestamps: number[] = [];
  private lastAnalysisTime = Date.now();
  private contentBuffer: Array<{ postId: string; element: Element; timestamp: number }> = [];

  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  // NLP-like patterns for basic content analysis
  private emotionPatterns = {
    positive: /\b(happy|joy|love|great|amazing|wonderful|excellent|good|nice|beautiful)\b/gi,
    negative: /\b(sad|angry|hate|terrible|awful|bad|horrible|disgusting|annoying)\b/gi,
    neutral: /\b(okay|fine|normal|average|standard|typical|regular)\b/gi
  };

  private complexityIndicators = {
    simple: /^[^.!?]*[.!?]$/,
    medium: /^[^.!?]*[.!?][^.!?]*[.!?]?$/,
    complex: /[.!?].*[.!?].*[.!?]/
  };

  constructor(config: EnhancedMetricsConfig, eventCallback: (event: UnifiedAnalyticsEvent) => void) {
    this.config = config;
    this.eventCallback = eventCallback;
    
    if (config.enableContentAnalysis) {
      this.initializeContentTracking();
    }
    
    this.startPeriodicAnalysis();
  }

  private initializeContentTracking(): void {
    // Observe new posts for content analysis
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node as Element;
            const postElement = element.querySelector('[data-post-id]') || 
                               (element.hasAttribute('data-post-id') ? element : null);
            
            if (postElement) {
              this.analyzeNewPost(postElement);
            }
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Analyze existing posts
    document.querySelectorAll('[data-post-id]').forEach(post => {
      this.analyzeNewPost(post);
    });
  }

  private analyzeNewPost(postElement: Element): void {
    const postId = postElement.getAttribute('data-post-id');
    if (!postId || this.postCharacteristics.has(postId)) return;

    const now = Date.now();
    this.postTimestamps.push(now);
    this.contentBuffer.push({ postId, element: postElement, timestamp: now });

    // Keep only recent timestamps (last 10 minutes)
    const tenMinutesAgo = now - 600000;
    this.postTimestamps = this.postTimestamps.filter(t => t > tenMinutesAgo);

    // Analyze post characteristics
    const characteristics = this.extractContentCharacteristics(postElement);
    this.postCharacteristics.set(postId, characteristics);

    // Track network effects
    const networkEffect = this.analyzeNetworkEffect(postElement);
    if (networkEffect) {
      this.networkEffects.set(postId, networkEffect);
    }

    // Update content velocity
    this.updateContentVelocity();

    // Analyze temporal patterns
    this.analyzeTemporalPattern(now);

    // Track immediate characteristics
    this.eventCallback({
      event_type: 'post_characteristics',
      event_category: 'content',
      event_priority: 'medium',
      post_id: postId,
      event_data: {
        text_length: characteristics.textLength,
        media_count: characteristics.mediaCount,
        hashtag_count: characteristics.hashtagCount,
        link_count: characteristics.linkCount,
        emotion_tone: characteristics.emotionTone,
        complexity: characteristics.complexity,
        language: characteristics.language,
        author_type: characteristics.authorType,
        content_density: this.calculateContentDensity(characteristics),
        engagement_potential: this.predictEngagementPotential(characteristics)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private extractContentCharacteristics(postElement: Element): ContentCharacteristics {
    const textContent = postElement.textContent || '';
    const mediaElements = postElement.querySelectorAll('img, video');
    const hashtags = textContent.match(/#\w+/g) || [];
    const links = postElement.querySelectorAll('a[href]');
    
    const emotionTone = this.analyzeEmotionTone(textContent);
    const complexity = this.analyzeComplexity(textContent);
    const language = this.detectLanguage(textContent);
    const authorType = this.inferAuthorType(postElement);

    return {
      textLength: textContent.length,
      mediaCount: mediaElements.length,
      hashtagCount: hashtags.length,
      linkCount: links.length,
      emotionTone,
      complexity,
      language,
      authorType
    };
  }

  private analyzeEmotionTone(text: string): string {
    const positiveMatches = (text.match(this.emotionPatterns.positive) || []).length;
    const negativeMatches = (text.match(this.emotionPatterns.negative) || []).length;
    const neutralMatches = (text.match(this.emotionPatterns.neutral) || []).length;

    const total = positiveMatches + negativeMatches + neutralMatches;
    if (total === 0) return 'neutral';

    const positiveRatio = positiveMatches / total;
    const negativeRatio = negativeMatches / total;

    if (positiveRatio > 0.6) return 'positive';
    if (negativeRatio > 0.6) return 'negative';
    if (positiveRatio > negativeRatio) return 'slightly_positive';
    if (negativeRatio > positiveRatio) return 'slightly_negative';
    return 'neutral';
  }

  private analyzeComplexity(text: string): 'simple' | 'medium' | 'complex' {
    if (text.length < 50) return 'simple';
    if (text.length > 500) return 'complex';

    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const avgWordsPerSentence = text.split(/\s+/).length / sentences.length;

    if (avgWordsPerSentence < 10) return 'simple';
    if (avgWordsPerSentence > 20) return 'complex';
    return 'medium';
  }

  private detectLanguage(text: string): string {
    // Simple heuristic-based language detection
    const englishWords = /\b(the|and|is|in|to|of|a|that|it|with|for|as|was|on|are|you)\b/gi;
    const englishMatches = (text.match(englishWords) || []).length;
    const totalWords = text.split(/\s+/).length;
    
    if (englishMatches / totalWords > 0.3) return 'en';
    return 'unknown';
  }

  private inferAuthorType(postElement: Element): 'friend' | 'page' | 'group' | 'unknown' {
    // Look for Facebook-specific indicators
    const authorElement = postElement.querySelector('[data-hovercard-object-id]') || 
                         postElement.querySelector('.actor-name') ||
                         postElement.querySelector('[data-ft*="page_id"]');

    if (!authorElement) return 'unknown';

    const hovercard = authorElement.getAttribute('data-hovercard-object-id');
    const dataFt = authorElement.getAttribute('data-ft');

    if (dataFt?.includes('page_id')) return 'page';
    if (dataFt?.includes('group_id')) return 'group';
    if (hovercard) return 'friend';
    
    return 'unknown';
  }

  private analyzeNetworkEffect(postElement: Element): NetworkEffect | null {
    const authorType = this.inferAuthorType(postElement);
    const authorElement = postElement.querySelector('[data-hovercard-object-id]') || 
                         postElement.querySelector('.actor-name');
    
    if (!authorElement) return null;

    const authorId = authorElement.getAttribute('data-hovercard-object-id') || 
                    authorElement.textContent?.trim() || 'unknown';

    return {
      authorType,
      authorId,
      connectionStrength: this.calculateConnectionStrength(authorType, authorElement),
      influenceScore: this.calculateInfluenceScore(postElement),
      contentPattern: this.identifyContentPattern(postElement)
    };
  }

  private updateContentVelocity(): void {
    const now = Date.now();
    const recentPosts = this.postTimestamps.filter(t => t > now - 60000); // Last minute
    
    this.contentVelocity.postsPerMinute = recentPosts.length;
    
    if (this.postTimestamps.length > 1) {
      const intervals = [];
      for (let i = 1; i < this.postTimestamps.length; i++) {
        intervals.push(this.postTimestamps[i] - this.postTimestamps[i - 1]);
      }
      this.contentVelocity.averageTimeBetweenPosts = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    }

    // Detect burst patterns
    this.detectBurstPatterns();

    this.eventCallback({
      event_type: 'content_velocity',
      event_category: 'content',
      event_priority: 'medium',
      event_data: {
        posts_per_minute: this.contentVelocity.postsPerMinute,
        average_interval_ms: this.contentVelocity.averageTimeBetweenPosts,
        burst_intensity: this.contentVelocity.burstPatterns.length,
        content_density: this.contentVelocity.contentDensity,
        feed_activity_level: this.categorizeActivityLevel(this.contentVelocity.postsPerMinute)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private detectBurstPatterns(): void {
    const now = Date.now();
    const intervals = [];
    
    for (let i = 1; i < this.postTimestamps.length; i++) {
      intervals.push(this.postTimestamps[i] - this.postTimestamps[i - 1]);
    }

    // Find sequences of short intervals (bursts)
    const shortIntervals = intervals.filter(interval => interval < 5000); // Less than 5 seconds
    this.contentVelocity.burstPatterns = shortIntervals;
  }

  private analyzeTemporalPattern(timestamp: number): void {
    const date = new Date(timestamp);
    const hour = date.getHours();
    const dayOfWeek = date.getDay();
    
    const seasonality = this.getSeasonality(hour);
    const userActivityLevel = this.assessUserActivityLevel();
    const contentFlowRate = this.calculateContentFlowRate();

    const pattern: TemporalPattern = {
      timeOfDay: hour,
      dayOfWeek,
      seasonality,
      userActivityLevel,
      contentFlowRate
    };

    this.temporalPatterns.push(pattern);

    // Keep only recent patterns (last 24 hours)
    const oneDayAgo = timestamp - 86400000;
    this.temporalPatterns = this.temporalPatterns.filter(p => 
      new Date().getTime() - (p.timeOfDay * 3600000) > oneDayAgo
    );

    this.eventCallback({
      event_type: 'temporal_patterns',
      event_category: 'content',
      event_priority: 'low',
      event_data: {
        time_of_day: hour,
        day_of_week: dayOfWeek,
        seasonality: seasonality,
        user_activity_level: userActivityLevel,
        content_flow_rate: contentFlowRate,
        peak_activity_hours: this.identifyPeakHours(),
        usage_pattern_consistency: this.calculatePatternConsistency()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private startPeriodicAnalysis(): void {
    setInterval(() => {
      this.performContentClustering();
      this.analyzeNetworkEffects();
      this.detectAnomalousPatterns();
    }, 300000); // Every 5 minutes
  }

  private performContentClustering(): void {
    if (this.postCharacteristics.size < 3) return;

    const posts = Array.from(this.postCharacteristics.entries());
    const clusters = this.clusterSimilarPosts(posts);

    clusters.forEach(cluster => {
      this.contentClusters.set(cluster.clusterId, cluster);
      
      this.eventCallback({
        event_type: 'content_similarity_clusters',
        event_category: 'content',
        event_priority: 'medium',
        event_data: {
          cluster_id: cluster.clusterId,
          cluster_theme: cluster.theme,
          post_count: cluster.postIds.length,
          similarity_score: cluster.similarity,
          detection_pattern: cluster.detectionPattern,
          cluster_characteristics: this.summarizeClusterCharacteristics(cluster),
          anomaly_score: this.calculateClusterAnomalyScore(cluster)
        },
        client_timestamp: new Date().toISOString()
      });
    });
  }

  private clusterSimilarPosts(posts: [string, ContentCharacteristics][]): ContentCluster[] {
    const clusters: ContentCluster[] = [];
    const processed = new Set<string>();

    posts.forEach(([postId, characteristics]) => {
      if (processed.has(postId)) return;

      const similarPosts = posts.filter(([otherId, otherChar]) => 
        !processed.has(otherId) && this.calculateSimilarity(characteristics, otherChar) > 0.7
      );

      if (similarPosts.length >= 2) {
        const cluster: ContentCluster = {
          clusterId: `cluster_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
          theme: this.identifyClusterTheme(similarPosts.map(p => p[1])),
          postIds: similarPosts.map(p => p[0]),
          similarity: this.calculateAverageSimilarity(similarPosts.map(p => p[1])),
          characteristics: similarPosts.map(p => p[1]),
          detectionPattern: 'consistent'
        };

        clusters.push(cluster);
        similarPosts.forEach(([id]) => processed.add(id));
      }
    });

    return clusters;
  }

  private analyzeNetworkEffects(): void {
    const effects = Array.from(this.networkEffects.values());
    if (effects.length === 0) return;

    // Analyze author type distribution
    const authorTypes = effects.reduce((acc, effect) => {
      acc[effect.authorType] = (acc[effect.authorType] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    // Calculate network influence metrics
    const avgInfluenceScore = effects.reduce((sum, e) => sum + e.influenceScore, 0) / effects.length;
    const networkDiversity = Object.keys(authorTypes).length;

    this.eventCallback({
      event_type: 'network_effects',
      event_category: 'content',
      event_priority: 'medium',
      event_data: {
        author_type_distribution: authorTypes,
        network_diversity_score: networkDiversity,
        average_influence_score: avgInfluenceScore,
        content_source_balance: this.calculateSourceBalance(authorTypes),
        algorithmic_bias_indication: this.detectAlgorithmicBias(effects)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private detectAnomalousPatterns(): void {
    // Detect unusual content patterns that might indicate AI content farming
    const recentPosts = Array.from(this.postCharacteristics.entries())
      .filter(([, char]) => Date.now() - this.lastAnalysisTime < 900000); // Last 15 minutes

    if (recentPosts.length < 5) return;

    const anomalies = this.identifyAnomalies(recentPosts);

    if (anomalies.length > 0) {
      this.eventCallback({
        event_type: 'content_anomaly_detected',
        event_category: 'content',
        event_priority: 'high',
        event_data: {
          anomaly_count: anomalies.length,
          anomaly_types: anomalies.map(a => a.type),
          confidence_scores: anomalies.map(a => a.confidence),
          pattern_description: this.describeAnomalousPattern(anomalies),
          potential_ai_farming: this.assessAIFarmingProbability(anomalies)
        },
        client_timestamp: new Date().toISOString()
      });
    }
  }

  // Helper methods
  private calculateContentDensity(characteristics: ContentCharacteristics): number {
    const totalElements = characteristics.textLength + 
                         (characteristics.mediaCount * 100) + 
                         (characteristics.hashtagCount * 10) + 
                         (characteristics.linkCount * 20);
    
    return Math.min(totalElements / 1000, 10);
  }

  private predictEngagementPotential(characteristics: ContentCharacteristics): number {
    let score = 0;
    
    // Text length factor
    if (characteristics.textLength > 50 && characteristics.textLength < 300) score += 20;
    
    // Media factor
    score += Math.min(characteristics.mediaCount * 15, 45);
    
    // Hashtag factor
    score += Math.min(characteristics.hashtagCount * 5, 25);
    
    // Emotion factor
    if (characteristics.emotionTone === 'positive') score += 10;
    else if (characteristics.emotionTone === 'negative') score += 5;
    
    return Math.min(score, 100);
  }

  private calculateConnectionStrength(authorType: string, authorElement: Element): number {
    // Simple heuristic based on author type and engagement indicators
    const baseStrengths = {
      friend: 0.8,
      page: 0.4,
      group: 0.6,
      unknown: 0.2
    };

    return baseStrengths[authorType as keyof typeof baseStrengths] || 0.2;
  }

  private calculateInfluenceScore(postElement: Element): number {
    // Look for engagement indicators (likes, shares, comments)
    const engagementElements = postElement.querySelectorAll('[aria-label*="reaction"], .comment, .share');
    return Math.min(engagementElements.length * 10, 100);
  }

  private identifyContentPattern(postElement: Element): string {
    const text = postElement.textContent || '';
    
    if (text.includes('🤖') || text.includes('AI')) return 'ai_related';
    if (text.match(/#\w+/g)?.length || 0 > 3) return 'hashtag_heavy';
    if (postElement.querySelectorAll('img, video').length > 2) return 'media_rich';
    if (text.length > 500) return 'long_form';
    
    return 'standard';
  }

  private getSeasonality(hour: number): 'morning' | 'afternoon' | 'evening' | 'night' {
    if (hour >= 6 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 18) return 'afternoon';
    if (hour >= 18 && hour < 22) return 'evening';
    return 'night';
  }

  private assessUserActivityLevel(): 'low' | 'medium' | 'high' {
    if (this.contentVelocity.postsPerMinute >= 5) return 'high';
    if (this.contentVelocity.postsPerMinute >= 2) return 'medium';
    return 'low';
  }

  private calculateContentFlowRate(): number {
    return this.contentVelocity.postsPerMinute * 10; // Normalized to 0-100 scale
  }

  private identifyPeakHours(): number[] {
    const hourCounts = new Array(24).fill(0);
    
    this.temporalPatterns.forEach(pattern => {
      hourCounts[pattern.timeOfDay]++;
    });

    // Find hours with above-average activity
    const average = hourCounts.reduce((a, b) => a + b, 0) / 24;
    return hourCounts
      .map((count, hour) => ({ hour, count }))
      .filter(({ count }) => count > average * 1.5)
      .map(({ hour }) => hour);
  }

  private calculatePatternConsistency(): number {
    if (this.temporalPatterns.length < 7) return 0.5; // Not enough data
    
    // Simple consistency measure based on activity level variance
    const activityLevels = this.temporalPatterns.map(p => p.contentFlowRate);
    const average = activityLevels.reduce((a, b) => a + b, 0) / activityLevels.length;
    const variance = activityLevels.reduce((sum, rate) => sum + Math.pow(rate - average, 2), 0) / activityLevels.length;
    
    return Math.max(0, 1 - variance / 100);
  }

  private calculateSimilarity(char1: ContentCharacteristics, char2: ContentCharacteristics): number {
    let similarity = 0;
    
    // Text length similarity
    const lengthDiff = Math.abs(char1.textLength - char2.textLength);
    const maxLength = Math.max(char1.textLength, char2.textLength);
    similarity += maxLength > 0 ? (1 - lengthDiff / maxLength) * 0.3 : 0.3;
    
    // Media count similarity
    if (char1.mediaCount === char2.mediaCount) similarity += 0.2;
    
    // Emotion tone similarity
    if (char1.emotionTone === char2.emotionTone) similarity += 0.2;
    
    // Complexity similarity
    if (char1.complexity === char2.complexity) similarity += 0.15;
    
    // Author type similarity
    if (char1.authorType === char2.authorType) similarity += 0.15;
    
    return similarity;
  }

  private calculateAverageSimilarity(characteristics: ContentCharacteristics[]): number {
    if (characteristics.length < 2) return 0;
    
    let totalSimilarity = 0;
    let comparisons = 0;
    
    for (let i = 0; i < characteristics.length - 1; i++) {
      for (let j = i + 1; j < characteristics.length; j++) {
        totalSimilarity += this.calculateSimilarity(characteristics[i], characteristics[j]);
        comparisons++;
      }
    }
    
    return comparisons > 0 ? totalSimilarity / comparisons : 0;
  }

  private identifyClusterTheme(characteristics: ContentCharacteristics[]): string {
    // Simple theme identification based on common characteristics
    const emotions = characteristics.map(c => c.emotionTone);
    const authorTypes = characteristics.map(c => c.authorType);
    const complexities = characteristics.map(c => c.complexity);
    
    const dominantEmotion = this.findMostCommon(emotions);
    const dominantAuthorType = this.findMostCommon(authorTypes);
    const dominantComplexity = this.findMostCommon(complexities);
    
    return `${dominantEmotion}_${dominantAuthorType}_${dominantComplexity}`;
  }

  private findMostCommon<T>(array: T[]): T {
    const counts = new Map<T, number>();
    array.forEach(item => {
      counts.set(item, (counts.get(item) || 0) + 1);
    });
    
    let mostCommon = array[0];
    let maxCount = 0;
    
    counts.forEach((count, item) => {
      if (count > maxCount) {
        maxCount = count;
        mostCommon = item;
      }
    });
    
    return mostCommon;
  }

  private summarizeClusterCharacteristics(cluster: ContentCluster): Record<string, unknown> {
    const chars = cluster.characteristics;
    
    return {
      avg_text_length: chars.reduce((sum, c) => sum + c.textLength, 0) / chars.length,
      total_media_count: chars.reduce((sum, c) => sum + c.mediaCount, 0),
      dominant_emotion: this.findMostCommon(chars.map(c => c.emotionTone)),
      dominant_complexity: this.findMostCommon(chars.map(c => c.complexity)),
      author_diversity: new Set(chars.map(c => c.authorType)).size
    };
  }

  private calculateClusterAnomalyScore(cluster: ContentCluster): number {
    // High similarity in a short time period might indicate artificial content
    const timeSpan = 300000; // 5 minutes
    const highSimilarityThreshold = 0.9;
    
    if (cluster.similarity > highSimilarityThreshold && cluster.postIds.length > 3) {
      return 0.8; // High anomaly score
    }
    
    return 0.2; // Low anomaly score
  }

  private categorizeActivityLevel(postsPerMinute: number): string {
    if (postsPerMinute >= 10) return 'very_high';
    if (postsPerMinute >= 5) return 'high';
    if (postsPerMinute >= 2) return 'medium';
    if (postsPerMinute >= 1) return 'low';
    return 'very_low';
  }

  private calculateSourceBalance(authorTypes: Record<string, number>): number {
    const total = Object.values(authorTypes).reduce((a, b) => a + b, 0);
    const distribution = Object.values(authorTypes).map(count => count / total);
    
    // Calculate entropy as a measure of balance
    const entropy = -distribution.reduce((sum, p) => sum + (p > 0 ? p * Math.log2(p) : 0), 0);
    const maxEntropy = Math.log2(Object.keys(authorTypes).length);
    
    return maxEntropy > 0 ? entropy / maxEntropy : 0;
  }

  private detectAlgorithmicBias(effects: NetworkEffect[]): string {
    const pageRatio = effects.filter(e => e.authorType === 'page').length / effects.length;
    const friendRatio = effects.filter(e => e.authorType === 'friend').length / effects.length;
    
    if (pageRatio > 0.7) return 'heavy_page_bias';
    if (friendRatio > 0.8) return 'heavy_friend_bias';
    if (pageRatio < 0.1 && friendRatio < 0.1) return 'unknown_source_bias';
    
    return 'balanced';
  }

  private identifyAnomalies(posts: [string, ContentCharacteristics][]): Array<{ type: string; confidence: number }> {
    const anomalies: Array<{ type: string; confidence: number }> = [];
    
    // Check for identical content characteristics
    const characteristicGroups = new Map<string, number>();
    posts.forEach(([, char]) => {
      const key = `${char.textLength}_${char.mediaCount}_${char.emotionTone}_${char.complexity}`;
      characteristicGroups.set(key, (characteristicGroups.get(key) || 0) + 1);
    });
    
    characteristicGroups.forEach((count, key) => {
      if (count >= 3) {
        anomalies.push({
          type: 'identical_characteristics',
          confidence: Math.min(count / 5, 1)
        });
      }
    });
    
    // Check for rapid posting from same author type
    const authorTypeCounts = posts.reduce((acc, [, char]) => {
      acc[char.authorType] = (acc[char.authorType] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    Object.entries(authorTypeCounts).forEach(([type, count]) => {
      if (count >= posts.length * 0.8 && posts.length >= 5) {
        anomalies.push({
          type: 'author_type_clustering',
          confidence: count / posts.length
        });
      }
    });
    
    return anomalies;
  }

  private describeAnomalousPattern(anomalies: Array<{ type: string; confidence: number }>): string {
    return anomalies.map(a => `${a.type}:${a.confidence.toFixed(2)}`).join(', ');
  }

  private assessAIFarmingProbability(anomalies: Array<{ type: string; confidence: number }>): number {
    const farmingIndicators = anomalies.filter(a => 
      a.type === 'identical_characteristics' || a.type === 'author_type_clustering'
    );
    
    if (farmingIndicators.length === 0) return 0;
    
    const avgConfidence = farmingIndicators.reduce((sum, a) => sum + a.confidence, 0) / farmingIndicators.length;
    return Math.min(avgConfidence * farmingIndicators.length / 2, 1);
  }

  public destroy(): void {
    this.postCharacteristics.clear();
    this.networkEffects.clear();
    this.contentClusters.clear();
    this.temporalPatterns = [];
    this.postTimestamps = [];
    this.contentBuffer = [];
  }
}