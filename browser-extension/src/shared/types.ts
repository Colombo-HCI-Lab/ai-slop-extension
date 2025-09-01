/**
 * Shared types for the browser extension
 */

export interface MetricsConfig {
  batchSize: number;
  flushInterval: number;
  enableDebugLogging: boolean;
  privacyMode: 'strict' | 'balanced' | 'full';
}

export interface AnalyticsEvent {
  type: string;
  category: string;
  value?: number;
  label?: string;
  metadata?: Record<string, unknown>;
  clientTimestamp: string;
}

export interface ScrollMetrics {
  totalDistance: number;
  pauseCount: number;
  primaryDirection: 'up' | 'down';
  averageSpeed: number;
}

export interface PostTrackingData {
  firstSeen: number;
  element: Element;
  hasIcon: boolean;
  interacted: boolean;
  iconVisibleDuration?: number;
  lastInteraction?: string;
}

export interface UserSession {
  userId: string;
  sessionId: string;
  startTime: number;
  lastActivity: number;
}

export interface ChatSession {
  id: string;
  postId: string;
  userId: string;
  startTime: number;
  messageCount: number;
  suggestedQuestionsUsed: number;
}

// Enhanced analytics event categories
export type EventCategory =
  | 'session'
  | 'post'
  | 'chat'
  | 'interaction'
  | 'performance'
  | 'behavior'
  | 'trust'
  | 'ui'
  | 'content'
  | 'learning';

export type EventPriority = 'critical' | 'high' | 'medium' | 'low';

// Unified analytics event for backend consolidation
export interface UnifiedAnalyticsEvent {
  event_type: string;
  event_category: EventCategory;
  event_priority?: EventPriority;
  user_id?: string;
  post_id?: string;
  session_id?: string;
  event_data: Record<string, unknown>;
  client_timestamp: string; // ISO
}

export interface EventBatchRequest {
  events: UnifiedAnalyticsEvent[];
}

// Enhanced metrics configurations
export interface EnhancedMetricsConfig extends MetricsConfig {
  enableMouseTracking: boolean;
  enableContentAnalysis: boolean;
  enableTrustTracking: boolean;
  enablePerformanceTracking: boolean;
  samplingRates: {
    scroll: number;
    mouse: number;
    performance: number;
  };
}

// Mouse behavior tracking
export interface MouseHoverData {
  elementId: string;
  hoverDuration: number;
  entryTime: number;
  exitTime: number;
  elementBounds: DOMRect;
  mouseTrail: { x: number; y: number; timestamp: number }[];
}

export interface AttentionMetrics {
  focusTime: number;
  blurTime: number;
  scrollPauses: number;
  readingSpeed: number; // chars per second
  attentionZones: { element: string; duration: number; depth: number }[];
}

// Trust and detection metrics
export interface TrustScore {
  currentScore: number;
  previousScore: number;
  factors: {
    accuracy: number;
    consistency: number;
    userFeedback: number;
    timeUsed: number;
  };
  lastUpdated: number;
}

export interface DetectionFeedback {
  postId: string;
  detectionResult: 'ai' | 'human' | 'uncertain';
  userFeedback: 'correct' | 'incorrect' | 'uncertain';
  confidence: number;
  feedbackTime: number;
}

// Content characteristics
export interface ContentCharacteristics {
  textLength: number;
  mediaCount: number;
  hashtagCount: number;
  linkCount: number;
  emotionTone: string;
  complexity: 'simple' | 'medium' | 'complex';
  language: string;
  authorType: 'friend' | 'page' | 'group' | 'unknown';
}

// Session learning metrics
export interface LearningMetrics {
  sessionNumber: number;
  accuracyImprovement: number;
  speedImprovement: number;
  confidenceGrowth: number;
  featureDiscoveryRate: number;
  sophisticationLevel: 'beginner' | 'intermediate' | 'advanced';
}

// Chat intelligence metrics
export interface ChatMetrics {
  questionTypes: string[];
  responseQuality: number;
  conversationDepth: number;
  topicTransitions: number;
  satisfactionIndicators: {
    messageEdits: number;
    followUpQuestions: number;
    positiveSignals: number;
    negativeSignals: number;
  };
}

// Performance tracking
export interface PerformanceMetrics {
  renderTime: number;
  memoryUsage: number;
  cpuUsage: number;
  networkLatency: number;
  errorRate: number;
  cacheHitRate: number;
}
