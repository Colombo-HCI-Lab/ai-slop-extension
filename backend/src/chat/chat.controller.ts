import {
  Body,
  Controller,
  HttpException,
  HttpStatus,
  Logger,
  Post,
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

  @Post()
  @ApiOperation({
    summary: 'Chat about a Facebook post',
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
