import { Global, Module } from '@nestjs/common';
import { LoggerService } from './logger.service';
import { ShutdownService } from './shutdown.service';

@Global()
@Module({
  providers: [LoggerService, ShutdownService],
  exports: [LoggerService, ShutdownService],
})
export class LoggerModule {}
