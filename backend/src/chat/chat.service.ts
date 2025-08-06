import { Injectable, Logger } from '@nestjs/common';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { ChatRequestDto } from './dto/chat-request.dto';
import { ChatResponseDto } from './dto/chat-response.dto';
import { LogContext, LoggerService } from '../logger/logger.service';
import { DatabaseService } from '../database/database.service';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);
  private readonly genAI: GoogleGenerativeAI;

  constructor(
    private readonly loggerService: LoggerService,
    private readonly databaseService: DatabaseService,
  ) {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error('GEMINI_API_KEY environment variable is required');
    }
    this.genAI = new GoogleGenerativeAI(apiKey);
  }

  async sendMessage(
    postId: string,
    message: string,
  ): Promise<{ id: string; message: string }> {
    // Save user message to database
    const userChat = await this.databaseService.chat.create({
      data: {
        postId,
        role: 'user',
        message,
      },
    });

    // Get post analysis data for context
    const post = await this.databaseService.post.findUnique({
      where: { id: postId },
    });

    if (!post) {
      throw new Error(`Post with ID ${postId} not found`);
    }

    // Get chat history for context
    const chatHistory = await this.databaseService.chat.findMany({
      where: { postId },
      orderBy: { createdAt: 'asc' },
      take: 20, // Limit to last 20 messages for context
    });

    // Build context for Gemini
    const systemPrompt = `You are an AI content detection assistant. You help users understand AI content detection results and answer questions about specific posts.

Post Analysis Context:
- Content: "${post.content.substring(0, 500)}..."
- Verdict: ${post.verdict}
- Confidence: ${(post.confidence * 100).toFixed(1)}%
- Explanation: ${post.explanation}
- Author: ${post.author || 'Unknown'}

Guidelines:
- Be helpful and informative about AI content detection
- Explain the reasoning behind the analysis
- Be honest about limitations and potential false positives
- Keep responses concise but informative
- Reference the specific post content when relevant`;

    // Build conversation history for context
    const conversationHistory = chatHistory
      .filter((chat) => chat.id !== userChat.id) // Exclude the message we just saved
      .map((chat) => `${chat.role}: ${chat.message}`)
      .join('\n');

    const fullPrompt = `${systemPrompt}

Previous conversation:
${conversationHistory}

User question: ${message}

Please provide a helpful response about the AI detection analysis.`;

    try {
      // Generate response with Gemini
      const model = this.genAI.getGenerativeModel({ model: 'gemini-pro' });
      const result = await model.generateContent(fullPrompt);
      const response = result.response;
      const responseText = response.text();

      // Save AI response to database
      const assistantChat = await this.databaseService.chat.create({
        data: {
          postId,
          role: 'assistant',
          message: responseText,
        },
      });

      this.loggerService.debug(`Generated chat response for post ${postId}`, {
        metadata: {
          userMessageLength: message.length,
          responseLength: responseText.length,
        },
      });

      return {
        id: assistantChat.id,
        message: responseText,
      };
    } catch (error) {
      this.loggerService.logError('Generate chat response', error as Error, {
        metadata: { postId, userMessage: message },
        requestId: 'chat-service',
        action: 'generate-response',
      });
      throw new Error('Failed to generate response');
    }
  }

  async getChatHistory(
    postId: string,
  ): Promise<
    Array<{ id: string; role: string; message: string; createdAt: Date }>
  > {
    const chats = await this.databaseService.chat.findMany({
      where: { postId },
      orderBy: { createdAt: 'asc' },
    });

    return chats.map((chat) => ({
      id: chat.id,
      role: chat.role,
      message: chat.message,
      createdAt: chat.createdAt,
    }));
  }

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
