/**
 * Chat Enhancement Analytics Tracker
 * Monitors conversation intelligence, question classification, response satisfaction, and chat evolution
 */

import type { 
  ChatMetrics, 
  UnifiedAnalyticsEvent,
  EnhancedMetricsConfig 
} from '@/shared/types';
import { createLogger } from '@/shared/logger';

const logger = createLogger('ChatAnalyticsTracker');

interface ConversationContext {
  sessionId: string;
  postId: string;
  startTime: number;
  messageCount: number;
  userMessages: string[];
  assistantMessages: string[];
  topicProgression: string[];
  satisfactionSignals: SatisfactionSignal[];
  questionTypes: QuestionClassification[];
  conversationDepth: number;
}

interface QuestionClassification {
  message: string;
  type: 'clarification' | 'exploration' | 'verification' | 'challenge' | 'follow_up' | 'meta';
  confidence: number;
  complexity: 'simple' | 'moderate' | 'complex';
  intent: 'information' | 'validation' | 'dispute' | 'curiosity' | 'help';
}

interface SatisfactionSignal {
  type: 'positive' | 'negative' | 'neutral';
  indicator: string;
  strength: number; // 0-1
  timestamp: number;
  context: string;
}

interface ResponseAnalysis {
  responseTime: number;
  messageLength: number;
  editCount: number;
  typoCount: number;
  sentimentScore: number;
  urgencyLevel: 'low' | 'medium' | 'high';
  coherenceScore: number;
}

interface ConversationFlow {
  transitions: Array<{
    from: string;
    to: string;
    trigger: string;
    timing: number;
  }>;
  depth: number;
  breadth: number;
  coherence: number;
  focus: 'narrow' | 'broad' | 'scattered';
}

export class ChatAnalyticsTracker {
  private activeConversations: Map<string, ConversationContext> = new Map();
  private conversationHistory: ConversationContext[] = [];
  private suggestionPerformance: Map<string, { clicks: number; satisfaction: number }> = new Map();
  
  private readonly config: EnhancedMetricsConfig;
  private eventCallback: (event: UnifiedAnalyticsEvent) => void;

  // NLP patterns for question classification
  private questionPatterns = {
    clarification: {
      patterns: [
        /what (do you mean|does this mean|is this)/i,
        /can you (explain|clarify|elaborate)/i,
        /i don't understand/i,
        /what exactly/i
      ],
      weight: 0.8
    },
    exploration: {
      patterns: [
        /(how does|why does|what if|what about)/i,
        /tell me more about/i,
        /what are the (implications|consequences|effects)/i,
        /how (would|could|might)/i
      ],
      weight: 0.7
    },
    verification: {
      patterns: [
        /(is this (true|correct|right)|are you sure)/i,
        /can you (confirm|verify)/i,
        /(really|actually)\?/i,
        /is it (possible|likely)/i
      ],
      weight: 0.9
    },
    challenge: {
      patterns: [
        /(but|however|although).*(wrong|incorrect|disagree)/i,
        /that('s| is) not (true|right|correct)/i,
        /(i think|i believe) (you're|this is) wrong/i,
        /how can you be sure/i
      ],
      weight: 1.0
    },
    follow_up: {
      patterns: [
        /and (then|what about|also)/i,
        /what (next|else|other)/i,
        /anything (else|more)/i,
        /follow.?up/i
      ],
      weight: 0.6
    }
  };

  // Sentiment indicators
  private sentimentIndicators = {
    positive: {
      patterns: [
        /thank(s| you)/i,
        /(great|good|helpful|useful|interesting)/i,
        /makes sense/i,
        /(got it|understand|clear)/i
      ],
      weight: 1
    },
    negative: {
      patterns: [
        /(confused|frustrat|annoyed|wrong|bad)/i,
        /(doesn't|don't) (help|work|make sense)/i,
        /still (don't|confused|lost)/i,
        /(waste of time|useless|unhelpful)/i
      ],
      weight: -1
    }
  };

  constructor(config: EnhancedMetricsConfig, eventCallback: (event: UnifiedAnalyticsEvent) => void) {
    this.config = config;
    this.eventCallback = eventCallback;
    
    this.initializeChatTracking();
  }

  private initializeChatTracking(): void {
    // Listen for chat-related DOM changes
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node as Element;
            
            // New chat message
            if (element.matches('.chat-message, .message')) {
              this.handleNewMessage(element);
            }
            
            // Chat window opened
            if (element.matches('.chat-window, .chat-container')) {
              this.handleChatStart(element);
            }
            
            // Suggested question clicked
            if (element.matches('.suggested-question, .quick-reply')) {
              this.handleSuggestionClick(element);
            }
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Listen for typing indicators
    document.addEventListener('input', (event) => {
      const target = event.target as Element;
      if (target.matches('.chat-input, textarea[data-chat]')) {
        this.handleTypingActivity(target);
      }
    });

    // Listen for message edits
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Backspace' || event.key === 'Delete') {
        const target = event.target as Element;
        if (target.matches('.chat-input, textarea[data-chat]')) {
          this.handleMessageEdit(target);
        }
      }
    });
  }

  public startConversation(sessionId: string, postId: string): void {
    const conversation: ConversationContext = {
      sessionId,
      postId,
      startTime: Date.now(),
      messageCount: 0,
      userMessages: [],
      assistantMessages: [],
      topicProgression: [],
      satisfactionSignals: [],
      questionTypes: [],
      conversationDepth: 0
    };

    this.activeConversations.set(sessionId, conversation);

    this.eventCallback({
      event_type: 'chat_conversation_start',
      event_category: 'chat',
      event_priority: 'high',
      post_id: postId,
      event_data: {
        session_id: sessionId,
        trigger_context: 'ai_detection_click',
        user_experience_level: this.inferUserExperience(),
        pre_chat_actions: this.getRecentUserActions()
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public trackUserMessage(sessionId: string, message: string, metadata: Record<string, unknown> = {}): void {
    const conversation = this.activeConversations.get(sessionId);
    if (!conversation) return;

    conversation.userMessages.push(message);
    conversation.messageCount++;

    // Classify the question
    const classification = this.classifyQuestion(message);
    conversation.questionTypes.push(classification);

    // Analyze response quality
    const responseAnalysis = this.analyzeUserResponse(message, metadata);

    // Update conversation depth
    conversation.conversationDepth = this.calculateConversationDepth(conversation);

    this.eventCallback({
      event_type: 'chat_user_message',
      event_category: 'chat',
      event_priority: 'high',
      event_data: {
        session_id: sessionId,
        message_count: conversation.messageCount,
        question_type: classification.type,
        question_complexity: classification.complexity,
        question_intent: classification.intent,
        classification_confidence: classification.confidence,
        message_length: message.length,
        response_analysis: responseAnalysis,
        conversation_depth: conversation.conversationDepth,
        topic_coherence: this.calculateTopicCoherence(conversation),
        engagement_level: this.assessEngagementLevel(responseAnalysis)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public trackAssistantMessage(sessionId: string, message: string, responseTime: number): void {
    const conversation = this.activeConversations.get(sessionId);
    if (!conversation) return;

    conversation.assistantMessages.push(message);
    conversation.messageCount++;

    // Detect topic transitions
    const topicTransition = this.detectTopicTransition(conversation, message);
    if (topicTransition) {
      conversation.topicProgression.push(topicTransition);
    }

    // Analyze response quality
    const responseQuality = this.analyzeAssistantResponseQuality(message, responseTime);

    this.eventCallback({
      event_type: 'chat_assistant_message',
      event_category: 'chat',
      event_priority: 'high',
      event_data: {
        session_id: sessionId,
        message_count: conversation.messageCount,
        response_time_ms: responseTime,
        message_length: message.length,
        response_quality: responseQuality,
        topic_transition: topicTransition || null,
        conversation_breadth: conversation.topicProgression.length,
        helpfulness_indicators: this.extractHelpfulnessIndicators(message)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public trackSatisfactionSignal(sessionId: string, signal: Partial<SatisfactionSignal>): void {
    const conversation = this.activeConversations.get(sessionId);
    if (!conversation) return;

    const fullSignal: SatisfactionSignal = {
      type: signal.type || 'neutral',
      indicator: signal.indicator || 'unknown',
      strength: signal.strength || 0.5,
      timestamp: Date.now(),
      context: signal.context || 'general'
    };

    conversation.satisfactionSignals.push(fullSignal);

    this.eventCallback({
      event_type: 'chat_satisfaction_signal',
      event_category: 'chat',
      event_priority: 'medium',
      event_data: {
        session_id: sessionId,
        signal_type: fullSignal.type,
        signal_indicator: fullSignal.indicator,
        signal_strength: fullSignal.strength,
        signal_context: fullSignal.context,
        cumulative_satisfaction: this.calculateCumulativeSatisfaction(conversation),
        satisfaction_trend: this.analyzeSatisfactionTrend(conversation)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public trackSuggestedQuestionPerformance(questionText: string, clicked: boolean, subsequentSatisfaction?: number): void {
    const performance = this.suggestionPerformance.get(questionText) || { clicks: 0, satisfaction: 0 };
    
    if (clicked) {
      performance.clicks++;
    }
    
    if (subsequentSatisfaction !== undefined) {
      performance.satisfaction = (performance.satisfaction + subsequentSatisfaction) / 2;
    }
    
    this.suggestionPerformance.set(questionText, performance);

    this.eventCallback({
      event_type: 'suggested_question_performance',
      event_category: 'chat',
      event_priority: 'medium',
      event_data: {
        question_text: questionText,
        click_count: performance.clicks,
        average_satisfaction: performance.satisfaction,
        performance_score: this.calculateSuggestionScore(performance),
        question_category: this.categorizeSuggestedQuestion(questionText),
        effectiveness_rating: this.rateSuggestionEffectiveness(performance)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  public endConversation(sessionId: string, endReason: string = 'user_close'): void {
    const conversation = this.activeConversations.get(sessionId);
    if (!conversation) return;

    const duration = Date.now() - conversation.startTime;
    const conversationFlow = this.analyzeConversationFlow(conversation);
    const finalMetrics = this.calculateFinalChatMetrics(conversation);

    // Move to history
    this.conversationHistory.push(conversation);
    this.activeConversations.delete(sessionId);

    this.eventCallback({
      event_type: 'chat_conversation_end',
      event_category: 'chat',
      event_priority: 'high',
      post_id: conversation.postId,
      event_data: {
        session_id: sessionId,
        duration_ms: duration,
        total_messages: conversation.messageCount,
        user_message_count: conversation.userMessages.length,
        assistant_message_count: conversation.assistantMessages.length,
        end_reason: endReason,
        conversation_flow: conversationFlow,
        final_satisfaction: finalMetrics.finalSatisfaction,
        topic_coverage: finalMetrics.topicCoverage,
        learning_outcome: this.assessLearningOutcome(conversation),
        user_sophistication_growth: this.measureSophisticationGrowth(conversation),
        conversation_value_score: this.calculateConversationValue(conversation)
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleNewMessage(element: Element): void {
    const sessionId = this.extractSessionId(element);
    const isUserMessage = element.classList.contains('user-message') || 
                         element.closest('.user-message') !== null;
    
    if (!sessionId) return;

    const messageText = element.textContent || '';
    
    if (isUserMessage) {
      this.trackUserMessage(sessionId, messageText);
    } else {
      // Assistant message - estimate response time
      const responseTime = this.estimateResponseTime(sessionId);
      this.trackAssistantMessage(sessionId, messageText, responseTime);
    }
  }

  private handleChatStart(element: Element): void {
    const postId = element.closest('[data-post-id]')?.getAttribute('data-post-id');
    const sessionId = this.generateSessionId();
    
    if (postId) {
      this.startConversation(sessionId, postId);
    }
  }

  private handleSuggestionClick(element: Element): void {
    const questionText = element.textContent || '';
    this.trackSuggestedQuestionPerformance(questionText, true);
  }

  private handleTypingActivity(element: Element): void {
    const sessionId = this.extractSessionId(element);
    if (!sessionId) return;

    // Track typing patterns for engagement analysis
    this.eventCallback({
      event_type: 'chat_typing_activity',
      event_category: 'chat',
      event_priority: 'low',
      event_data: {
        session_id: sessionId,
        input_length: (element as HTMLInputElement).value.length,
        typing_speed: this.estimateTypingSpeed(element),
        engagement_indicator: 'active_composition'
      },
      client_timestamp: new Date().toISOString()
    });
  }

  private handleMessageEdit(element: Element): void {
    const sessionId = this.extractSessionId(element);
    if (!sessionId) return;

    // Track message edits as refinement behavior
    this.trackSatisfactionSignal(sessionId, {
      type: 'neutral',
      indicator: 'message_refinement',
      strength: 0.6,
      context: 'editing'
    });
  }

  private classifyQuestion(message: string): QuestionClassification {
    let bestMatch: {
      type: QuestionClassification['type'];
      confidence: number;
      patterns: RegExp[];
    } = {
      type: 'follow_up',
      confidence: 0,
      patterns: [] as RegExp[]
    };

    // Check each question type
    Object.entries(this.questionPatterns).forEach(([type, config]) => {
      const matches = config.patterns.filter(pattern => pattern.test(message)).length;
      const confidence = (matches / config.patterns.length) * config.weight;
      
      if (confidence > bestMatch.confidence) {
        bestMatch = {
          type: type as QuestionClassification['type'],
          confidence,
          patterns: config.patterns
        };
      }
    });

    return {
      message,
      type: bestMatch.type,
      confidence: bestMatch.confidence,
      complexity: this.assessQuestionComplexity(message),
      intent: this.inferQuestionIntent(message)
    };
  }

  private analyzeUserResponse(message: string, metadata: Record<string, unknown>): ResponseAnalysis {
    const typoCount = this.estimateTypoCount(message);
    const sentimentScore = this.analyzeSentiment(message);
    
    return {
      responseTime: (metadata.responseTime as number) || 0,
      messageLength: message.length,
      editCount: (metadata.editCount as number) || 0,
      typoCount,
      sentimentScore,
      urgencyLevel: this.assessUrgency(message),
      coherenceScore: this.assessCoherence(message)
    };
  }

  private analyzeAssistantResponseQuality(message: string, responseTime: number): {
    informativeness: number;
    clarity: number;
    relevance: number;
    timeliness: number;
  } {
    return {
      informativeness: this.assessInformativeness(message),
      clarity: this.assessClarity(message),
      relevance: 0.8, // Would need context to assess properly
      timeliness: responseTime < 3000 ? 1 : Math.max(0, 1 - (responseTime - 3000) / 10000)
    };
  }

  private calculateConversationDepth(conversation: ConversationContext): number {
    // Simple heuristic based on question types and follow-ups
    const depthFactors = {
      clarification: 1,
      exploration: 2,
      verification: 1.5,
      challenge: 3,
      follow_up: 0.5,
      meta: 1
    };

    const totalDepth = conversation.questionTypes.reduce((sum, q) => 
      sum + depthFactors[q.type], 0
    );

    return Math.min(totalDepth / conversation.questionTypes.length || 0, 5);
  }

  private detectTopicTransition(conversation: ConversationContext, message: string): string | null {
    if (conversation.assistantMessages.length < 2) return null;

    // Simple topic detection based on keyword changes
    const previousKeywords = this.extractKeywords(conversation.assistantMessages.slice(-2, -1)[0]);
    const currentKeywords = this.extractKeywords(message);
    
    const overlap = previousKeywords.filter(kw => currentKeywords.includes(kw)).length;
    const overlapRatio = overlap / Math.max(previousKeywords.length, currentKeywords.length);
    
    if (overlapRatio < 0.3) {
      return `${previousKeywords[0] || 'unknown'}_to_${currentKeywords[0] || 'unknown'}`;
    }
    
    return null;
  }

  private analyzeConversationFlow(conversation: ConversationContext): ConversationFlow {
    const transitions = [];
    
    // Analyze question type transitions
    for (let i = 1; i < conversation.questionTypes.length; i++) {
      transitions.push({
        from: conversation.questionTypes[i - 1].type,
        to: conversation.questionTypes[i].type,
        trigger: 'user_question',
        timing: 0 // Would need timestamps
      });
    }

    return {
      transitions,
      depth: conversation.conversationDepth,
      breadth: conversation.topicProgression.length,
      coherence: this.calculateTopicCoherence(conversation),
      focus: this.assessConversationFocus(transitions)
    };
  }

  private calculateFinalChatMetrics(conversation: ConversationContext): {
    finalSatisfaction: number;
    topicCoverage: number;
  } {
    const finalSatisfaction = this.calculateCumulativeSatisfaction(conversation);
    const topicCoverage = Math.min(conversation.topicProgression.length / 3, 1); // Max 3 topics
    
    return { finalSatisfaction, topicCoverage };
  }

  // Helper methods
  private extractSessionId(element: Element): string | null {
    return element.closest('[data-session-id]')?.getAttribute('data-session-id') || null;
  }

  private generateSessionId(): string {
    return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  }

  private estimateResponseTime(sessionId: string): number {
    // Placeholder - would track actual timing
    return Math.random() * 5000 + 1000; // 1-6 seconds
  }

  private estimateTypingSpeed(element: Element): number {
    // Simple heuristic - would need more sophisticated tracking
    return 50 + Math.random() * 100; // 50-150 WPM
  }

  private assessQuestionComplexity(message: string): 'simple' | 'moderate' | 'complex' {
    if (message.length < 20) return 'simple';
    if (message.split('?').length > 2) return 'complex';
    if (message.includes('because') || message.includes('however')) return 'complex';
    if (message.length > 100) return 'moderate';
    return 'simple';
  }

  private inferQuestionIntent(message: string): QuestionClassification['intent'] {
    if (/^(is|are|can|do|does|will|would)/.test(message.toLowerCase())) return 'validation';
    if (/(wrong|incorrect|disagree|but)/.test(message.toLowerCase())) return 'dispute';
    if (/(help|how|what|explain)/.test(message.toLowerCase())) return 'help';
    if (/(interesting|curious|wonder)/.test(message.toLowerCase())) return 'curiosity';
    return 'information';
  }

  private estimateTypoCount(message: string): number {
    // Simple heuristic - would use spell checking
    const suspiciousPatterns = [
      /\b\w*\d\w*\b/g, // Words with numbers
      /\b\w{1,2}\b/g,  // Very short words
      /(\w)\1{3,}/g    // Repeated characters
    ];
    
    return suspiciousPatterns.reduce((count, pattern) => 
      count + (message.match(pattern) || []).length, 0
    );
  }

  private analyzeSentiment(message: string): number {
    let score = 0;
    
    Object.values(this.sentimentIndicators).forEach(indicator => {
      indicator.patterns.forEach(pattern => {
        if (pattern.test(message)) {
          score += indicator.weight;
        }
      });
    });
    
    return Math.max(-1, Math.min(1, score / 5));
  }

  private assessUrgency(message: string): 'low' | 'medium' | 'high' {
    const urgencyIndicators = [
      /urgent|asap|quickly|immediately/i,
      /!{2,}/,
      /CAPS.*CAPS/,
      /(need|want).*(now|right now|immediately)/i
    ];
    
    const matches = urgencyIndicators.filter(pattern => pattern.test(message)).length;
    
    if (matches >= 2) return 'high';
    if (matches >= 1) return 'medium';
    return 'low';
  }

  private assessCoherence(message: string): number {
    // Simple coherence assessment based on sentence structure
    const sentences = message.split(/[.!?]+/).filter(s => s.trim());
    if (sentences.length === 0) return 0;
    
    const avgWordsPerSentence = message.split(/\s+/).length / sentences.length;
    
    // Coherence heuristic: 8-25 words per sentence is optimal
    if (avgWordsPerSentence >= 8 && avgWordsPerSentence <= 25) return 1;
    if (avgWordsPerSentence >= 5 && avgWordsPerSentence <= 35) return 0.7;
    return 0.4;
  }

  private assessInformativeness(message: string): number {
    // Heuristic based on content richness
    const factors = {
      length: Math.min(message.length / 200, 1),
      specificity: (message.match(/\d+|\b(specific|exactly|precisely)\b/gi) || []).length / 10,
      examples: (message.match(/\b(example|instance|such as|like)\b/gi) || []).length / 5
    };
    
    return Math.min((factors.length + factors.specificity + factors.examples) / 3, 1);
  }

  private assessClarity(message: string): number {
    // Simple clarity assessment
    const clarity = 1 - (this.estimateTypoCount(message) / message.length * 100);
    return Math.max(0, Math.min(1, clarity));
  }

  private extractKeywords(text: string): string[] {
    // Simple keyword extraction
    const words = text.toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/)
      .filter(word => word.length > 3);
    
    // Remove common words (simple stop words)
    const stopWords = new Set(['this', 'that', 'with', 'have', 'will', 'from', 'they', 'been']);
    
    return words.filter(word => !stopWords.has(word)).slice(0, 5);
  }

  private calculateTopicCoherence(conversation: ConversationContext): number {
    if (conversation.questionTypes.length < 2) return 1;
    
    // Measure consistency in question types
    const typeCounts = new Map<string, number>();
    conversation.questionTypes.forEach(q => {
      typeCounts.set(q.type, (typeCounts.get(q.type) || 0) + 1);
    });
    
    const maxTypeCount = Math.max(...typeCounts.values());
    return maxTypeCount / conversation.questionTypes.length;
  }

  private assessConversationFocus(transitions: any[]): 'narrow' | 'broad' | 'scattered' {
    if (transitions.length < 2) return 'narrow';
    
    const uniqueTransitions = new Set(transitions.map(t => `${t.from}-${t.to}`)).size;
    const transitionVariety = uniqueTransitions / transitions.length;
    
    if (transitionVariety < 0.3) return 'narrow';
    if (transitionVariety > 0.7) return 'scattered';
    return 'broad';
  }

  private calculateCumulativeSatisfaction(conversation: ConversationContext): number {
    if (conversation.satisfactionSignals.length === 0) return 0.5;
    
    const weightedSatisfaction = conversation.satisfactionSignals.reduce((sum, signal) => {
      const value = signal.type === 'positive' ? 1 : signal.type === 'negative' ? -1 : 0;
      return sum + (value * signal.strength);
    }, 0);
    
    return Math.max(0, Math.min(1, (weightedSatisfaction / conversation.satisfactionSignals.length + 1) / 2));
  }

  private analyzeSatisfactionTrend(conversation: ConversationContext): string {
    if (conversation.satisfactionSignals.length < 3) return 'insufficient_data';
    
    const recent = conversation.satisfactionSignals.slice(-3);
    const early = conversation.satisfactionSignals.slice(0, 3);
    
    const recentAvg = recent.reduce((sum, s) => sum + (s.type === 'positive' ? 1 : s.type === 'negative' ? -1 : 0), 0) / recent.length;
    const earlyAvg = early.reduce((sum, s) => sum + (s.type === 'positive' ? 1 : s.type === 'negative' ? -1 : 0), 0) / early.length;
    
    const improvement = recentAvg - earlyAvg;
    
    if (improvement > 0.3) return 'improving';
    if (improvement < -0.3) return 'declining';
    return 'stable';
  }

  private calculateSuggestionScore(performance: { clicks: number; satisfaction: number }): number {
    const clickScore = Math.min(performance.clicks / 10, 1); // Normalize clicks
    const satisfactionScore = performance.satisfaction;
    
    return (clickScore * 0.3 + satisfactionScore * 0.7);
  }

  private categorizeSuggestedQuestion(question: string): string {
    if (/what.*(is|are|does|means)/i.test(question)) return 'definition';
    if (/how.*(does|to|can)/i.test(question)) return 'process';
    if (/(why|because|reason)/i.test(question)) return 'explanation';
    if (/(example|instance)/i.test(question)) return 'example';
    return 'general';
  }

  private rateSuggestionEffectiveness(performance: { clicks: number; satisfaction: number }): string {
    const score = this.calculateSuggestionScore(performance);
    
    if (score >= 0.8) return 'highly_effective';
    if (score >= 0.6) return 'effective';
    if (score >= 0.4) return 'moderately_effective';
    return 'ineffective';
  }

  private inferUserExperience(): string {
    // Based on historical conversation data
    if (this.conversationHistory.length === 0) return 'new_user';
    if (this.conversationHistory.length < 5) return 'beginner';
    if (this.conversationHistory.length < 20) return 'intermediate';
    return 'experienced';
  }

  private getRecentUserActions(): string[] {
    // Placeholder - would track actual recent actions
    return ['post_view', 'icon_hover', 'detection_result'];
  }

  private assessEngagementLevel(analysis: ResponseAnalysis): string {
    const factors = [
      analysis.messageLength > 50 ? 1 : 0,
      analysis.coherenceScore > 0.7 ? 1 : 0,
      analysis.typoCount < 2 ? 1 : 0,
      analysis.editCount > 0 ? 1 : 0 // Shows thoughtfulness
    ];
    
    const score = factors.reduce((a, b) => a + b, 0) / factors.length;
    
    if (score >= 0.75) return 'high';
    if (score >= 0.5) return 'medium';
    return 'low';
  }

  private extractHelpfulnessIndicators(message: string): string[] {
    const indicators = [];
    
    if (/(here's|this is|you can|try)/i.test(message)) indicators.push('actionable');
    if (/(example|for instance|such as)/i.test(message)) indicators.push('examples_provided');
    if (/(because|since|due to)/i.test(message)) indicators.push('explanatory');
    if (message.length > 200) indicators.push('comprehensive');
    if (/(link|url|resource)/i.test(message)) indicators.push('references_provided');
    
    return indicators;
  }

  private assessLearningOutcome(conversation: ConversationContext): string {
    const endingSatisfaction = this.calculateCumulativeSatisfaction(conversation);
    const conversationDepth = conversation.conversationDepth;
    
    if (endingSatisfaction > 0.7 && conversationDepth > 2) return 'high_learning';
    if (endingSatisfaction > 0.5 && conversationDepth > 1) return 'moderate_learning';
    if (endingSatisfaction > 0.3) return 'basic_learning';
    return 'minimal_learning';
  }

  private measureSophisticationGrowth(conversation: ConversationContext): number {
    if (conversation.questionTypes.length < 3) return 0;
    
    const early = conversation.questionTypes.slice(0, 2);
    const late = conversation.questionTypes.slice(-2);
    
    const complexityScore = (questions: QuestionClassification[]) => {
      return questions.reduce((sum, q) => {
        const scores = { simple: 1, moderate: 2, complex: 3 };
        return sum + scores[q.complexity];
      }, 0) / questions.length;
    };
    
    return complexityScore(late) - complexityScore(early);
  }

  private calculateConversationValue(conversation: ConversationContext): number {
    const factors = {
      depth: Math.min(conversation.conversationDepth / 3, 1),
      breadth: Math.min(conversation.topicProgression.length / 5, 1),
      satisfaction: this.calculateCumulativeSatisfaction(conversation),
      length: Math.min(conversation.messageCount / 10, 1)
    };
    
    return (factors.depth * 0.3 + factors.breadth * 0.2 + factors.satisfaction * 0.4 + factors.length * 0.1);
  }

  public getChatMetrics(sessionId: string): ChatMetrics | null {
    const conversation = this.activeConversations.get(sessionId);
    if (!conversation) return null;

    return {
      questionTypes: conversation.questionTypes.map(q => q.type),
      responseQuality: this.calculateCumulativeSatisfaction(conversation),
      conversationDepth: conversation.conversationDepth,
      topicTransitions: conversation.topicProgression.length,
      satisfactionIndicators: {
        messageEdits: conversation.satisfactionSignals.filter(s => s.indicator === 'message_refinement').length,
        followUpQuestions: conversation.questionTypes.filter(q => q.type === 'follow_up').length,
        positiveSignals: conversation.satisfactionSignals.filter(s => s.type === 'positive').length,
        negativeSignals: conversation.satisfactionSignals.filter(s => s.type === 'negative').length
      }
    };
  }

  public destroy(): void {
    this.activeConversations.clear();
    this.suggestionPerformance.clear();
  }
}