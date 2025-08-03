import { Module } from '@nestjs/common';
import { WinstonModule } from 'nest-winston';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ChatModule } from './chat/chat.module';
import { DetectModule } from './detect/detect.module';
import { LoggerService } from './logger/logger.service';
import { winstonConfig } from './logger/logger.config';

@Module({
  imports: [WinstonModule.forRoot(winstonConfig), ChatModule, DetectModule],
  controllers: [AppController],
  providers: [AppService, LoggerService],
  exports: [LoggerService],
})
export class AppModule {}
