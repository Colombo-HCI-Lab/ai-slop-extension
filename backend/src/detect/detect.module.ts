import { Module } from '@nestjs/common';
import { DetectController } from './detect.controller';
import { DetectService } from './detect.service';
import { CacheService } from './cache.service';
import { LoggerService } from '../logger/logger.service';

@Module({
  controllers: [DetectController],
  providers: [DetectService, CacheService, LoggerService],
})
export class DetectModule {}
