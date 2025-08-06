import {
  Body,
  Controller,
  HttpException,
  HttpStatus,
  Logger,
  Post,
  Get,
  Param,
  Req,
  UsePipes,
  ValidationPipe,
} from '@nestjs/common';
import type { Request } from 'express';
import {
  ApiOperation,
  ApiResponse,
  ApiTags,
  ApiBadRequestResponse,
  ApiInternalServerErrorResponse,
} from '@nestjs/swagger';
import { ChatService } from './chat.service';
import { ChatRequestDto } from './dto/chat-request.dto';
import { ChatResponseDto } from './dto/chat-response.dto';
import { LoggerService } from '../logger/logger.service';

@ApiTags('chat')
@Controller('api/v1/chat')
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(
    private readonly chatService: ChatService,
    private readonly loggerService: LoggerService,
  ) {}

  @Post('message')
  @ApiOperation({
    summary: 'Send a chat message about a post',
    description:
      'Send a message and get a response using Gemini AI about the analyzed post',
  })
  @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
  async sendMessage(
    @Body() body: { postId: string; message: string },
    @Req() req: Request,
  ) {
    const requestId =
      (req as Request & { requestId?: string }).requestId || 'unknown';
    const context = {
      requestId,
      postId: body.postId,
      action: 'send_message',
    };

    this.loggerService.log(`Sending message for post: ${body.postId}`, {
      ...context,
      metadata: { messageLength: body.message.length },
    });

    try {
      const response = await this.chatService.sendMessage(
        body.postId,
        body.message,
      );
      return response;
    } catch (error) {
      this.loggerService.logError('Send message', error as Error, context);
      throw new HttpException(
        'Failed to send message',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Get('history/:postId')
  @ApiOperation({
    summary: 'Get chat history for a post',
    description: 'Retrieve all chat messages for a specific analyzed post',
  })
  async getChatHistory(@Param('postId') postId: string, @Req() req: Request) {
    const requestId =
      (req as Request & { requestId?: string }).requestId || 'unknown';
    const context = {
      requestId,
      postId,
      action: 'get_chat_history',
    };

    this.loggerService.log(`Getting chat history for post: ${postId}`, context);

    try {
      const history = await this.chatService.getChatHistory(postId);
      return { messages: history };
    } catch (error) {
      this.loggerService.logError('Get chat history', error as Error, context);
      throw new HttpException(
        'Failed to get chat history',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  @Post()
  @ApiOperation({
    summary: 'Chat about a Facebook post (legacy)',
    description:
      'Allows users to have a conversation about a specific Facebook post and its AI slop analysis',
  })
  @ApiResponse({
    status: 200,
    description: 'Chat response generated successfully',
    type: ChatResponseDto,
  })
  @ApiBadRequestResponse({
    description: 'Invalid request data',
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
    description: 'Internal server error',
    schema: {
      type: 'object',
      properties: {
        statusCode: { type: 'number', example: 500 },
        message: {
          type: 'string',
          example: 'Chat service temporarily unavailable',
        },
        error: { type: 'string', example: 'Internal Server Error' },
      },
    },
  })
  @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
  async chat(
    @Body() request: ChatRequestDto,
    @Req() req: Request,
  ): Promise<ChatResponseDto> {
    const requestId =
      (req as Request & { requestId?: string }).requestId || 'unknown';
    const context = {
      requestId,
      postId: request.postId,
      action: 'chat_generation',
    };

    this.loggerService.log(
      `Received chat request for post: ${request.postId}`,
      {
        ...context,
        metadata: {
          messageLength: request.message.length,
        },
      },
    );

    try {
      const startTime = Date.now();
      const response = await this.chatService.generateChatResponse(
        request,
        context,
      );
      const processingTime = Date.now() - startTime;

      this.loggerService.log(
        `Chat response generated successfully for post: ${request.postId}`,
        {
          ...context,
          metadata: {
            processingTime,
            responseLength: response.response.length,
          },
        },
      );

      return response;
    } catch (error: unknown) {
      this.loggerService.logError('Chat generation', error as Error, context);

      if (error instanceof HttpException) {
        throw error;
      }

      throw new HttpException(
        {
          statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
          message: 'An error occurred while generating chat response',
          error: 'Internal Server Error',
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
