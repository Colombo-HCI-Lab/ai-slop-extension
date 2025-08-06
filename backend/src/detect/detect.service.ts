import { Injectable, Logger } from '@nestjs/common';
import { DetectDto } from './dto/detect.dto';
import { LogContext, LoggerService } from '../logger/logger.service';
import { DatabaseService } from '../database/database.service';
import { CacheService } from './cache.service';

@Injectable()
export class DetectService {
  private readonly logger = new Logger(DetectService.name);
  private requestCounter = 0;

  constructor(
    private readonly loggerService: LoggerService,
    private readonly databaseService: DatabaseService,
    private readonly cacheService: CacheService,
  ) {}

  async detect(
    detectDto: DetectDto,
    context?: LogContext,
  ): Promise<{
    postId: string;
    verdict: 'ai_slop' | 'human_content' | 'uncertain';
    confidence: number;
    explanation: string;
    timestamp: string;
    debugInfo: {
      mode: string;
      requestNumber: number;
      randomValue?: string;
      indicatorCount?: number;
      fromCache?: boolean;
    };
  }> {
    const { content, postId } = detectDto;
    this.requestCounter++;

    const serviceContext = {
      ...context,
      metadata: {
        ...context?.metadata,
        requestNumber: this.requestCounter,
        contentLength: content.length,
      },
    };

    this.loggerService.debug(
      `[Request #${this.requestCounter}] Analyzing post ${postId}`,
      serviceContext,
    );

    // Check cache first
    const cachedResult = await this.cacheService.getCachedResult(
      detectDto,
      serviceContext,
    );

    if (cachedResult) {
      // Return cached result with updated debug info
      const response = {
        postId: cachedResult.postId,
        verdict: cachedResult.verdict,
        confidence: cachedResult.confidence,
        explanation: cachedResult.explanation,
        timestamp: cachedResult.timestamp,
        debugInfo: {
          mode: 'cached_result',
          requestNumber: this.requestCounter,
          fromCache: true,
        },
      };

      this.loggerService.log(
        `[Request #${this.requestCounter}] Returning cached result for post ${postId}`,
        {
          ...serviceContext,
          metadata: {
            ...serviceContext.metadata,
            cached: true,
            verdict: cachedResult.verdict,
            confidence: Math.round(cachedResult.confidence * 100),
          },
        },
      );

      return response;
    }

    this.loggerService.debug(
      `Content preview: ${content.substring(0, 100)}...`,
      serviceContext,
    );

    // TESTING MODE: Randomly determine if content is AI slop
    const isRandomMode = true; // Toggle this for testing vs real detection

    if (isRandomMode) {
      // Random detection for UI testing
      const randomValue = Math.random();
      const isAiSlop = randomValue > 0.5;
      const confidence = isAiSlop
        ? 0.65 + Math.random() * 0.35 // 65-100% for AI slop
        : 0.15 + Math.random() * 0.35; // 15-50% for human content

      const verdict: 'ai_slop' | 'human_content' | 'uncertain' = isAiSlop
        ? 'ai_slop'
        : 'human_content';

      const aiExplanations = [
        'Content exhibits repetitive phrasing and generic language patterns typical of AI generation',
        'Detected multiple AI-typical markers including formulaic expressions and lack of personal voice',
        'Writing style shows signs of automated generation with predictable sentence structures',
        'Content lacks authentic human experiences and uses overly formal language patterns',
      ];

      const humanExplanations = [
        'Content shows natural language variations and personal voice',
        'Writing exhibits genuine human experiences and emotional authenticity',
        'Text contains colloquialisms and natural conversational flow',
        'Content displays unique perspective and spontaneous expression',
      ];

      const explanation = isAiSlop
        ? aiExplanations[Math.floor(Math.random() * aiExplanations.length)]
        : humanExplanations[
            Math.floor(Math.random() * humanExplanations.length)
          ];

      this.loggerService.log(
        `[Request #${this.requestCounter}] Random mode - Verdict: ${verdict} (${Math.round(confidence * 100)}%)`,
        {
          ...serviceContext,
          metadata: {
            ...serviceContext.metadata,
            mode: 'random_testing',
            randomValue: randomValue.toFixed(3),
            verdict,
            confidence: Math.round(confidence * 100),
          },
        },
      );

      const response = {
        postId,
        verdict,
        confidence,
        explanation,
        timestamp: new Date().toISOString(),
        debugInfo: {
          mode: 'random_testing',
          requestNumber: this.requestCounter,
          randomValue: randomValue.toFixed(3),
        },
      };

      this.loggerService.verbose(
        `[Request #${this.requestCounter}] Response generated`,
        {
          ...serviceContext,
          metadata: {
            ...serviceContext.metadata,
            response: JSON.stringify(response),
          },
        },
      );

      // Save analysis to cache
      try {
        await this.cacheService.saveResult(
          detectDto,
          { verdict, confidence, explanation },
          serviceContext,
        );
      } catch (error) {
        this.loggerService.logError(
          `Cache save failed (Request #${this.requestCounter})`,
          error as Error,
          {
            ...serviceContext,
            requestId: serviceContext?.requestId || 'detect-service',
            action: 'cache-save',
          },
        );
      }

      return response;
    }

    // Real AI detection logic (preserved for production use)
    const aiIndicators = [
      'it is important to note',
      'in conclusion',
      'moreover',
      'furthermore',
      'it should be noted',
      'delve into',
      'tapestry',
      'navigate',
      'landscape',
      'realm',
      'embark',
      'journey',
      'pivotal',
      'paramount',
      'unprecedented',
      'revolutionize',
      'cutting-edge',
      'seamlessly',
      'robust solution',
      'leveraging',
    ];

    const contentLower = content.toLowerCase();
    const matchedIndicators = aiIndicators.filter((indicator) =>
      contentLower.includes(indicator),
    );

    this.loggerService.debug(
      `[Request #${this.requestCounter}] Matched indicators: ${matchedIndicators.join(', ') || 'none'}`,
      {
        ...serviceContext,
        metadata: {
          ...serviceContext.metadata,
          matchedIndicators,
          indicatorCount: matchedIndicators.length,
        },
      },
    );

    const indicatorScore = matchedIndicators.length;
    const confidence = Math.min(0.95, 0.2 + indicatorScore * 0.15);

    let verdict: 'ai_slop' | 'human_content' | 'uncertain';
    if (indicatorScore >= 3) {
      verdict = 'ai_slop';
    } else if (indicatorScore === 0) {
      verdict = 'human_content';
    } else {
      verdict = 'uncertain';
    }

    const explanation =
      indicatorScore > 0
        ? `Detected ${indicatorScore} AI-typical phrase(s): ${matchedIndicators.slice(0, 3).join(', ')}${matchedIndicators.length > 3 ? '...' : ''}`
        : 'No AI-typical patterns detected';

    this.loggerService.log(
      `[Request #${this.requestCounter}] Real detection - Verdict: ${verdict} (${Math.round(confidence * 100)}%)`,
      {
        ...serviceContext,
        metadata: {
          ...serviceContext.metadata,
          mode: 'real_detection',
          verdict,
          confidence: Math.round(confidence * 100),
          indicatorCount: indicatorScore,
        },
      },
    );

    const response = {
      postId,
      verdict,
      confidence,
      explanation,
      timestamp: new Date().toISOString(),
      debugInfo: {
        mode: 'real_detection',
        requestNumber: this.requestCounter,
        indicatorCount: indicatorScore,
      },
    };

    this.loggerService.verbose(
      `[Request #${this.requestCounter}] Response generated`,
      {
        ...serviceContext,
        metadata: {
          ...serviceContext.metadata,
          response: JSON.stringify(response),
        },
      },
    );

    // Save analysis to cache
    try {
      await this.cacheService.saveResult(
        detectDto,
        { verdict, confidence, explanation },
        serviceContext,
      );
    } catch (error) {
      this.loggerService.logError(
        `Cache save failed (Request #${this.requestCounter})`,
        error as Error,
        {
          ...serviceContext,
          requestId: serviceContext?.requestId || 'detect-service',
          action: 'cache-save',
        },
      );
    }

    return response;
  }
}
