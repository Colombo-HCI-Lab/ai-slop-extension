import { Module } from '@nestjs/common';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import { LoggerService } from '../logger/logger.service';

@Module({
  controllers: [ChatController],
  providers: [ChatService, LoggerService],
  exports: [ChatService],
})
export class ChatModule {}
