import { ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty, IsString, IsOptional, IsObject } from 'class-validator';

export class ChatRequestDto {
  @ApiProperty({
    description: 'The unique identifier of the Facebook post',
    example: 'fb-post-123456',
  })
  @IsNotEmpty()
  @IsString()
  postId: string;

  @ApiProperty({
    description: 'The user message/question about the post',
    example: 'Why do you think this is AI generated?',
  })
  @IsNotEmpty()
  @IsString()
  message: string;

  @ApiProperty({
    description: 'The original content of the Facebook post',
    example: 'This is an amazing discovery that will change everything...',
  })
  @IsNotEmpty()
  @IsString()
  postContent: string;

  @ApiProperty({
    description: 'Previous AI slop analysis result',
    required: false,
    example: {
      isAiSlop: true,
      confidence: 0.85,
      reasoning: 'Repetitive patterns detected',
    },
  })
  @IsOptional()
  @IsObject()
  previousAnalysis?: {
    isAiSlop: boolean;
    confidence: number;
    reasoning: string;
  };

  @ApiProperty({
    description: 'Conversation history',
    required: false,
    example: [
      { role: 'user', content: 'Is this really AI?' },
      { role: 'assistant', content: 'Yes, based on several indicators...' },
    ],
  })
  @IsOptional()
  conversationHistory?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}
