import { Controller, Post, Body, Logger, Req } from '@nestjs/common';
import type { Request } from 'express';
import { DetectService } from './detect.service';
import { DetectDto } from './dto/detect.dto';
import { LoggerService } from '../logger/logger.service';

@Controller('api/v1/detect')
export class DetectController {
  private readonly logger = new Logger(DetectController.name);

  constructor(
    private readonly detectService: DetectService,
    private readonly loggerService: LoggerService,
  ) {}

  @Post('analyze')
  async detect(@Body() detectDto: DetectDto, @Req() request: Request) {
    const requestId =
      (request as Request & { requestId?: string }).requestId || 'unknown';
    const context = {
      requestId,
      postId: detectDto.postId,
      action: 'ai_detection',
    };

    this.loggerService.log(
      `Received detection request for post: ${detectDto.postId}`,
      context,
    );

    this.loggerService.logContentExtraction(
      detectDto.postId,
      detectDto.content?.length || 0,
      context,
    );

    try {
      const startTime = Date.now();
      const result = await this.detectService.detect(detectDto, context);
      const processingTime = Date.now() - startTime;

      this.loggerService.logAiAnalysis(
        detectDto.postId,
        result.verdict,
        Math.round(result.confidence * 100),
        {
          ...context,
          metadata: {
            processingTime,
            contentLength: detectDto.content?.length || 0,
          },
        },
      );

      return result;
    } catch (error: unknown) {
      this.loggerService.logError('Detection', error as Error, context);
      throw error;
    }
  }
}
