import { Global, Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { PluginLoaderService } from './plugin-loader.service';
import { PluginStorageService } from './plugin-storage.service';
import { ConversationMapping } from '../../modules/integration/entities/conversation-mapping.entity';
import { ConversationMappingService } from '../../modules/integration/conversation-mapping.service';
import { PLUGIN_CONVERSATION_MAPPING_PORT } from './plugin-host-ports';

@Global() // Make plugin services available everywhere
@Module({
  imports: [TypeOrmModule.forFeature([ConversationMapping], 'data')],
  // ConversationMappingService lives here (its own module never provides it) and is reached by the
  // plugin runtime only through the core-owned port token, resolved lazily via ModuleRef by
  // PluginHostServices — so neither the service nor the port needs re-exporting.
  providers: [
    PluginStorageService,
    PluginLoaderService,
    ConversationMappingService,
    // An alias, not a factory, so lifecycle hooks are not dispatched twice on the same instance.
    { provide: PLUGIN_CONVERSATION_MAPPING_PORT, useExisting: ConversationMappingService },
  ],
  exports: [PluginLoaderService, PluginStorageService],
})
export class PluginsModule {}
