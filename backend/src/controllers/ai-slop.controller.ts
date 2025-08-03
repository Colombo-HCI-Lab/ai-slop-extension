import {
  Body,
  Controller,
  HttpException,
  HttpStatus,
  Logger,
  Post,
  UsePipes,
  ValidationPipe,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiInternalServerErrorResponse,
  ApiOperation,
  ApiResponse,
  ApiTags,
} from '@nestjs/swagger';
import { AiAnalysisService } from '../services/ai-analysis.service';
import { AnalyzeRequestDto } from '../dto/analyze-request.dto';
import { AnalyzeResponseDto } from '../dto/analyze-response.dto';

/**
 * Controller responsible for handling AI slop detection requests
 * Provides REST API endpoints for AI-generated content analysis
 */
@ApiTags('ai-slop')
@Controller('api/v1/ai-slop')
export class AiSlopController {
  private readonly logger = new Logger(AiSlopController.name);

  constructor(private readonly aiAnalysisService: AiAnalysisService) {}

  /**
   * Main endpoint for analyzing content to detect AI-generated slop
   * Accepts text content and optional media URLs for comprehensive analysis
   *
   * @param request Analysis request containing content and optional media URLs
   * @returns Analysis result indicating whether content is AI-generated slop
   */
  @Post('detect')
  @ApiOperation({
    summary: 'Detect AI-generated slop content',
    description:
      'Analyzes text content and optional media (images/videos) to determine if they are AI-generated slop content. Returns a boolean result with confidence score and detailed reasoning.',
  })
  @ApiResponse({
    status: 200,
    description: 'Analysis completed successfully',
    type: AnalyzeResponseDto,
  })
  @ApiBadRequestResponse({
    description: 'Invalid request data (validation errors)',
    schema: {
      type: 'object',
      properties: {
        statusCode: { type: 'number', example: 400 },
        message: { type: 'array', items: { type: 'string' } },
        error: { type: 'string', example: 'Bad Request' },
      },
    },
  })
  @ApiInternalServerErrorResponse({
    description: 'Internal server error during analysis',
    schema: {
      type: 'object',
      properties: {
        statusCode: { type: 'number', example: 500 },
        message: {
          type: 'string',
          example: 'Analysis service temporarily unavailable',
        },
        error: { type: 'string', example: 'Internal Server Error' },
      },
    },
  })
  @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
  analyzeContent(@Body() request: AnalyzeRequestDto): AnalyzeResponseDto {
    this.logger.log(
      `Received analysis request for content length: ${request.content?.length || 0} characters`,
    );

    try {
      // Log request details (excluding sensitive content)
      this.logger.debug(`Analysis request details: {
        hasImageUrl: ${!!request.imageUrl},
        hasVideoUrl: ${!!request.videoUrl},
        contentPreview: "${request.content?.substring(0, 50)}...",
        metadata: ${JSON.stringify(request.metadata || {})}
      }`);

      // Perform the analysis
      const result = this.aiAnalysisService.analyzeContent(request);

      // Log successful analysis
      this.logger.log(
        `Analysis completed successfully. Result: ${result.isAiSlop ? 'AI Slop' : 'Human Content'} (confidence: ${result.confidence})`,
      );

      return result;
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      const errorStack = error instanceof Error ? error.stack : undefined;
      this.logger.error(`Analysis failed: ${errorMessage}`, errorStack);

      // Handle different types of errors
      if (error instanceof HttpException) {
        throw error;
      }

      // Handle validation errors
      if (error instanceof Error && error.name === 'ValidationError') {
        throw new HttpException(
          {
            statusCode: HttpStatus.BAD_REQUEST,
            message: 'Validation failed',
            details: error.message,
          },
          HttpStatus.BAD_REQUEST,
        );
      }

      // Handle service unavailable errors
      if (
        error instanceof Error &&
        (error.message.includes('service unavailable') ||
          error.message.includes('timeout'))
      ) {
        throw new HttpException(
          {
            statusCode: HttpStatus.SERVICE_UNAVAILABLE,
            message:
              'Analysis service temporarily unavailable. Please try again later.',
            error: 'Service Unavailable',
          },
          HttpStatus.SERVICE_UNAVAILABLE,
        );
      }

      // Generic internal server error
      throw new HttpException(
        {
          statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
          message: 'An unexpected error occurred during analysis',
          error: 'Internal Server Error',
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
