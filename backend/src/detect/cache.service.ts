import { Injectable, Logger } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { LogContext, LoggerService } from '../logger/logger.service';
import { DetectDto } from './dto/detect.dto';
import { createHash } from 'crypto';

export interface CachedDetectionResult {
  postId: string;
  verdict: 'ai_slop' | 'human_content' | 'uncertain';
  confidence: number;
  explanation: string;
  timestamp: string;
  fromCache: boolean;
}

@Injectable()
export class CacheService {
  private readonly logger = new Logger(CacheService.name);

  constructor(
    private readonly databaseService: DatabaseService,
    private readonly loggerService: LoggerService,
  ) {}

  /**
   * Generate a cache key based on post content to detect duplicate content
   * even if postId is different (e.g., same post viewed by different users)
   */
  generateCacheKey(content: string, postId?: string): string {
    // Normalize content for consistent hashing
    const normalizedContent = content
      .toLowerCase()
      .replace(/\s+/g, ' ') // Normalize whitespace
      .trim();

    // Create content hash
    const contentHash = createHash('sha256')
      .update(normalizedContent)
      .digest('hex')
      .substring(0, 16); // Use first 16 chars for shorter key

    return `content:${contentHash}`;
  }

  /**
   * Check if a detection result exists in cache (database)
   */
  async getCachedResult(
    detectDto: DetectDto,
    context?: LogContext,
  ): Promise<CachedDetectionResult | null> {
    const { postId, content } = detectDto;

    try {
      // Try to find by exact postId
      const cachedPost = await this.databaseService.post.findUnique({
        where: { postId },
      });

      if (cachedPost) {
        this.loggerService.debug(
          `Found cached result by postId for post ${postId}`,
          {
            ...context,
            metadata: {
              ...context?.metadata,
              matchType: 'post_id',
            },
          },
        );

        const result: CachedDetectionResult = {
          postId,
          verdict: cachedPost.verdict as
            | 'ai_slop'
            | 'human_content'
            | 'uncertain',
          confidence: cachedPost.confidence,
          explanation: cachedPost.explanation || '',
          timestamp: cachedPost.updatedAt.toISOString(),
          fromCache: true,
        };

        this.loggerService.log(
          `Cache HIT for post ${postId} - ${cachedPost.verdict} (${Math.round(cachedPost.confidence * 100)}%)`,
          {
            ...context,
            metadata: {
              ...context?.metadata,
              cacheAge: Date.now() - cachedPost.updatedAt.getTime(),
            },
          },
        );

        return result;
      }

      this.loggerService.debug(`Cache MISS for post ${postId}`, {
        ...context,
        metadata: {
          ...context?.metadata,
          contentLength: content.length,
        },
      });

      return null;
    } catch (error) {
      this.loggerService.logError('Cache lookup failed', error as Error, {
        ...context,
        requestId: context?.requestId || 'cache-service',
        action: 'cache_lookup',
        metadata: {
          ...context?.metadata,
          postId,
        },
      });
      return null;
    }
  }

  /**
   * Save detection result to cache (database)
   */
  async saveResult(
    detectDto: DetectDto,
    result: {
      verdict: 'ai_slop' | 'human_content' | 'uncertain';
      confidence: number;
      explanation: string;
    },
    context?: LogContext,
  ): Promise<void> {
    const { postId, content, author, metadata } = detectDto;

    try {
      await this.databaseService.post.upsert({
        where: { postId },
        update: {
          verdict: result.verdict,
          confidence: result.confidence,
          explanation: result.explanation,
          updatedAt: new Date(),
        },
        create: {
          postId,
          content,
          author,
          verdict: result.verdict,
          confidence: result.confidence,
          explanation: result.explanation,
          metadata,
        },
      });

      this.loggerService.debug(`Cached result for post ${postId}`, {
        ...context,
        metadata: {
          ...context?.metadata,
          verdict: result.verdict,
          confidence: Math.round(result.confidence * 100),
        },
      });
    } catch (error) {
      this.loggerService.logError('Cache save failed', error as Error, {
        ...context,
        requestId: context?.requestId || 'cache-service',
        action: 'cache_save',
        metadata: {
          ...context?.metadata,
          postId,
        },
      });
      throw error;
    }
  }

  /**
   * Get cache statistics
   */
  async getCacheStats(): Promise<{
    totalCachedPosts: number;
    aiSlopCount: number;
    humanContentCount: number;
    uncertainCount: number;
    oldestEntry: Date | null;
    newestEntry: Date | null;
  }> {
    try {
      const [totalCount, verdictCounts, dateRange] = await Promise.all([
        this.databaseService.post.count(),
        this.databaseService.post.groupBy({
          by: ['verdict'],
          _count: {
            verdict: true,
          },
        }),
        this.databaseService.post.aggregate({
          _min: {
            createdAt: true,
          },
          _max: {
            createdAt: true,
          },
        }),
      ]);

      const verdictStats = verdictCounts.reduce(
        (acc, { verdict, _count }) => {
          acc[verdict] = _count.verdict;
          return acc;
        },
        {} as Record<string, number>,
      );

      return {
        totalCachedPosts: totalCount,
        aiSlopCount: verdictStats['ai_slop'] || 0,
        humanContentCount: verdictStats['human_content'] || 0,
        uncertainCount: verdictStats['uncertain'] || 0,
        oldestEntry: dateRange._min.createdAt,
        newestEntry: dateRange._max.createdAt,
      };
    } catch (error) {
      this.logger.error('Failed to get cache statistics', error);
      throw error;
    }
  }

  /**
   * Clear old cache entries (optional cleanup method)
   */
  async clearOldEntries(olderThanDays: number = 30): Promise<number> {
    try {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

      const result = await this.databaseService.post.deleteMany({
        where: {
          createdAt: {
            lt: cutoffDate,
          },
        },
      });

      this.logger.log(
        `Cleared ${result.count} cache entries older than ${olderThanDays} days`,
      );

      return result.count;
    } catch (error) {
      this.logger.error('Failed to clear old cache entries', error);
      throw error;
    }
  }
}
