import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUrl,
  MaxLength,
} from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

/**
 * Data Transfer Object for AI slop analysis requests
 * Validates incoming request data for content analysis
 */
export class AnalyzeRequestDto {
  @ApiProperty({
    description: 'Text content of the post to analyze',
    example:
      'This is an amazing breakthrough in AI technology that will revolutionize everything!',
    maxLength: 10000,
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(10000, { message: 'Post content cannot exceed 10,000 characters' })
  content: string;

  @ApiPropertyOptional({
    description: 'Optional URL of an image associated with the post',
    example: 'https://example.com/image.jpg',
  })
  @IsOptional()
  @IsUrl({}, { message: 'Image URL must be a valid URL' })
  imageUrl?: string;

  @ApiPropertyOptional({
    description: 'Optional URL of a video associated with the post',
    example: 'https://example.com/video.mp4',
  })
  @IsOptional()
  @IsUrl({}, { message: 'Video URL must be a valid URL' })
  videoUrl?: string;

  @ApiPropertyOptional({
    description: 'Optional metadata about the post for analysis context',
  })
  @IsOptional()
  metadata?: {
    author?: string;
    timestamp?: string;
    platform?: string;
    postType?: 'text' | 'image' | 'video' | 'mixed';
  };
}
