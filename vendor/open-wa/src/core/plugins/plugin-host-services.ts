import type { ModuleRef } from '@nestjs/core';
import {
  PLUGIN_CONVERSATION_MAPPING_PORT,
  PLUGIN_INSTANCE_PORT,
  PLUGIN_MESSAGE_PORT,
  PLUGIN_SEARCH_REGISTRY_PORT,
  PLUGIN_SESSION_PORT,
  type PluginConversationMappingPort,
  type PluginInstancePort,
  type PluginMessagePort,
  type PluginSearchRegistryPort,
  type PluginSessionPort,
} from './plugin-host-ports';

/**
 * Resolves the host services a plugin capability reaches, at call time rather than at module load.
 *
 * Every lookup is a non-strict `ModuleRef.get` against a core-owned port token from
 * plugin-host-ports.ts, and the deferral is load-bearing: constructor injection would close the
 * provider cycle
 * `PluginLoaderService -> SessionService -> SessionEngineLifecycle -> EngineFactory -> PluginLoaderService`.
 * Resolving the PORT tokens rather than the feature-module service classes also means this file
 * names no feature module at all — no static import edge, and no lazy `require` either. The module
 * that owns each service registers the token adapter, so the binding lives with the service while
 * core/plugins depends only on its own tokens.
 *
 * Keeping the lookups in one place means the loader never has to carry that reasoning, nor name the
 * five ports it was resolving. Everything below is a resolution detail; nothing here decides policy.
 */
export class PluginHostServices {
  constructor(private readonly moduleRef: ModuleRef) {}

  getMessagePort(): PluginMessagePort {
    return this.moduleRef.get<typeof PLUGIN_MESSAGE_PORT, PluginMessagePort>(PLUGIN_MESSAGE_PORT, { strict: false });
  }

  getSessionPort(): PluginSessionPort {
    return this.moduleRef.get<typeof PLUGIN_SESSION_PORT, PluginSessionPort>(PLUGIN_SESSION_PORT, { strict: false });
  }

  getConversationMappingPort(): PluginConversationMappingPort {
    return this.moduleRef.get<typeof PLUGIN_CONVERSATION_MAPPING_PORT, PluginConversationMappingPort>(
      PLUGIN_CONVERSATION_MAPPING_PORT,
      { strict: false },
    );
  }

  getPluginInstancePort(): PluginInstancePort {
    return this.moduleRef.get<typeof PLUGIN_INSTANCE_PORT, PluginInstancePort>(PLUGIN_INSTANCE_PORT, {
      strict: false,
    });
  }

  /**
   * Search is conditionally loaded (`SEARCH_ENABLED=false` omits SearchModule), so the port adapter
   * may not be registered at all. Returns undefined in that case so callers can no-op rather than throw.
   */
  getSearchRegistryPort(): PluginSearchRegistryPort | undefined {
    try {
      return this.moduleRef.get<typeof PLUGIN_SEARCH_REGISTRY_PORT, PluginSearchRegistryPort>(
        PLUGIN_SEARCH_REGISTRY_PORT,
        { strict: false },
      );
    } catch {
      return undefined;
    }
  }
}
