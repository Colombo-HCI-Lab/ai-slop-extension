import { Injectable, Logger } from '@nestjs/common';
import { ChatRequestDto } from './dto/chat-request.dto';
import { ChatResponseDto } from './dto/chat-response.dto';
import { LogContext, LoggerService } from '../logger/logger.service';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(private readonly loggerService: LoggerService) {}

  generateChatResponse(
    request: ChatRequestDto,
    context?: LogContext,
  ): Promise<ChatResponseDto> {
    this.loggerService.debug(
      `Generating chat response for post: ${request.postId}`,
      {
        ...context,
        metadata: {
          messageLength: request.message.length,
          userMessage: request.message.substring(0, 100),
        },
      },
    );

    // For now, implement a mock response
    // In production, this would integrate with an LLM API
    const response = this.generateMockResponse(request, context);

    return Promise.resolve({
      response,
      suggestedQuestions: this.generateSuggestedQuestions(request),
      context: {
        sources: [
          'Content analysis',
          'Pattern recognition',
          'Language modeling',
        ],
        confidence: request.previousAnalysis?.confidence || 0.75,
        additionalInfo:
          'This analysis is based on multiple AI detection patterns',
      },
      timestamp: new Date().toISOString(),
    });
  }

  private generateMockResponse(
    request: ChatRequestDto,
    context?: LogContext,
  ): string {
    const { message, previousAnalysis } = request;

    // Simple response generation based on the message
    if (message.toLowerCase().includes('why')) {
      if (previousAnalysis?.isAiSlop) {
        return `This post was identified as AI-generated content because: ${previousAnalysis.reasoning}. The content shows typical AI patterns such as overly generic language, repetitive sentence structures, and lack of genuine personal experiences.`;
      } else {
        return 'The post appears to be human-written based on its natural language patterns, personal anecdotes, and authentic writing style.';
      }
    }

    if (
      message.toLowerCase().includes('sure') ||
      message.toLowerCase().includes('confident')
    ) {
      return `The confidence level for this analysis is ${(previousAnalysis?.confidence || 0.75) * 100}%. This is based on multiple factors including language patterns, content structure, and stylistic elements.`;
    }

    if (message.toLowerCase().includes('false positive')) {
      return 'While our AI detection system is highly accurate, false positives can occur. Human writing that is very formal, uses common phrases, or follows predictable patterns might be mistakenly flagged. If you believe this is incorrect, you can choose to ignore this analysis.';
    }

    // Default response
    const defaultResponse = `I can help you understand the AI detection analysis for this post. The system has analyzed various aspects of the content including writing style, language patterns, and structural elements. Feel free to ask specific questions about the analysis.`;

    this.loggerService.debug('Generated mock response', {
      ...context,
      metadata: {
        responseType: 'default',
        responseLength: defaultResponse.length,
      },
    });

    return defaultResponse;
  }

  private generateSuggestedQuestions(request: ChatRequestDto): string[] {
    const questions = [
      'What specific patterns indicate this is AI-generated?',
      'How confident are you in this analysis?',
      'Could this be a false positive?',
      'What are the key indicators of AI-generated content?',
    ];

    if (request.previousAnalysis?.isAiSlop) {
      questions.push('What makes this different from human writing?');
    } else {
      questions.push('Why do you think this is human-written?');
    }

    // Return 3 random questions
    return questions.sort(() => Math.random() - 0.5).slice(0, 3);
  }
}
