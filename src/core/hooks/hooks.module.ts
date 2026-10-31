import { Global, Module } from '@nestjs/common';
import { HookManager } from './hook-manager.service';

@Global() // Make HookManager available everywhere without importing
@Module({
  providers: [HookManager],
  exports: [HookManager],
})
export class HooksModule {}
