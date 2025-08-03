import { ApiProperty } from '@nestjs/swagger';

/**
 * Data Transfer Object for AI slop analysis responses
 * Standardizes the format of analysis results returned to clients
 */
export class AnalyzeResponseDto {
  @ApiProperty({
    description: 'Whether the content is determined to be AI-generated slop',
    example: true,
  })
  isAiSlop: boolean;

  @ApiProperty({
    description: 'Confidence score of the analysis (0-1)',
    example: 0.85,
    minimum: 0,
    maximum: 1,
  })
  confidence: number;

  @ApiProperty({
    description: 'Human-readable explanation of the analysis result',
    example:
      'This content shows typical patterns of AI-generated text including repetitive phrases and generic language.',
  })
  reasoning: string;

  @ApiProperty({
    description: 'Detailed analysis features that contributed to the decision',
    example: {
      textAnalysis: {
        repetitivePatterns: true,
        genericLanguage: true,
        sentimentConsistency: false,
      },
      imageAnalysis: {
        aiGenerated: false,
        analyzed: false,
      },
      videoAnalysis: {
        aiGenerated: false,
        analyzed: false,
      },
    },
  })
  analysisDetails: {
    textAnalysis: {
      repetitivePatterns: boolean;
      genericLanguage: boolean;
      sentimentConsistency: boolean;
      vocabularyComplexity: 'low' | 'medium' | 'high';
      grammarQuality: 'poor' | 'average' | 'good' | 'excellent';
    };
    imageAnalysis?: {
      aiGenerated: boolean;
      analyzed: boolean;
      confidence?: number;
      artifacts?: string[];
    };
    videoAnalysis?: {
      aiGenerated: boolean;
      analyzed: boolean;
      confidence?: number;
      artifacts?: string[];
    };
  };

  @ApiProperty({
    description: 'Processing time in milliseconds',
    example: 245,
  })
  processingTime: number;

  @ApiProperty({
    description: 'Timestamp when the analysis was completed',
    example: '2023-12-07T10:30:00.000Z',
  })
  timestamp: string;
}
