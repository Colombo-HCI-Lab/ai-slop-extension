import { IsString, IsOptional, IsObject } from 'class-validator';

export class AnalyzePostDto {
  @IsString()
  postId: string;

  @IsString()
  content: string;

  @IsOptional()
  @IsString()
  author?: string;

  @IsOptional()
  @IsObject()
  metadata?: any;
}

export class PostAnalysisResponse {
  id: string;
  postId: string;
  verdict: string;
  confidence: number;
  explanation?: string;
  createdAt: Date;
}
