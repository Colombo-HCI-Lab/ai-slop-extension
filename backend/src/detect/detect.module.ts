import { Module } from '@nestjs/common';
import { DetectController } from './detect.controller';
import { DetectService } from './detect.service';
import { LoggerService } from '../logger/logger.service';

@Module({
  controllers: [DetectController],
  providers: [DetectService, LoggerService],
})
export class DetectModule {}
