import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AiSlopController } from './controllers/ai-slop.controller';
import { AiAnalysisService } from './services/ai-analysis.service';

@Module({
  imports: [],
  controllers: [AppController, AiSlopController],
  providers: [AppService, AiAnalysisService],
})
export class AppModule {}
