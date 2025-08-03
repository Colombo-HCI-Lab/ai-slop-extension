import { ApiProperty } from '@nestjs/swagger';

export class ChatResponseDto {
  @ApiProperty({
    description: 'The AI assistant response',
    example:
      'Based on the analysis, this post shows clear signs of AI generation...',
  })
  response: string;

  @ApiProperty({
    description: 'Suggested follow-up questions',
    example: [
      'What specific patterns indicate AI generation?',
      'Could this be a false positive?',
      'How confident are you in this analysis?',
    ],
  })
  suggestedQuestions: string[];

  @ApiProperty({
    description: 'Additional context or references',
    required: false,
    example: {
      sources: ['Pattern analysis', 'Language model signatures'],
      confidence: 0.85,
    },
  })
  context?: {
    sources?: string[];
    confidence?: number;
    additionalInfo?: string;
  };

  @ApiProperty({
    description: 'Timestamp of the response',
    example: '2023-12-07T10:30:00.000Z',
  })
  timestamp: string;
}
