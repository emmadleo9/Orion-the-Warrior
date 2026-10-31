import {
  Injectable,
  Module,
  OnApplicationBootstrap,
  OnModuleDestroy,
  OnModuleInit,
  type Provider,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { PluginsModule } from './plugins.module';
import { IntegrationModule } from '../../modules/integration/integration.module';
import { MessageModule } from '../../modules/message/message.module';
import { SearchModule } from '../../modules/search/search.module';
import { SessionModule } from '../../modules/session/session.module';

/**
 * Every PLUGIN_*_PORT must be registered with `useExisting`, never a factory that returns the
 * service instance. Nest dispatches onModuleInit/onApplicationBootstrap/onModuleDestroy once per
 * non-alias provider, and only `useExisting` is an alias: a factory port ran SessionService's
 * hooks twice, launching two concurrent auto-start loops on every boot. The same applies to any other
 * factory that returns an injected instance (search.module.ts `SEARCH_BOOTSTRAP` returns the registry):
 * harmless while the target has no lifecycle hook, doubled the moment one is added.
 *
 * `useExisting` is typed `any`, so unlike the factory it replaced it does NOT check that the service
 * still satisfies the port. That check lives on the classes instead: each one carries
 * `implements Plugin*Port`, so a signature drift fails `tsc --noEmit` rather than surfacing as a
 * runtime TypeError inside a plugin capability call.
 */
describe('plugin host port providers', () => {
  const MODULES = [PluginsModule, IntegrationModule, MessageModule, SearchModule, SessionModule];

  it('registers every PLUGIN_*_PORT as a useExisting alias', () => {
    const ports: string[] = [];
    for (const module of MODULES) {
      const providers = (Reflect.getMetadata('providers', module) as unknown[] | undefined) ?? [];
      for (const provider of providers) {
        if (typeof provider !== 'object' || provider === null || !('provide' in provider)) continue;
        const token = provider.provide;
        const name = typeof token === 'symbol' ? (token.description ?? '') : '';
        if (!/^PLUGIN_.*_PORT$/.test(name)) continue;
        ports.push(name);
        expect({ port: name, alias: 'useExisting' in provider, factory: 'useFactory' in provider }).toEqual({
          port: name,
          alias: true,
          factory: false,
        });
      }
    }
    expect(ports.sort()).toEqual([
      'PLUGIN_CONVERSATION_MAPPING_PORT',
      'PLUGIN_INSTANCE_PORT',
      'PLUGIN_MESSAGE_PORT',
      'PLUGIN_SEARCH_REGISTRY_PORT',
      'PLUGIN_SESSION_PORT',
    ]);
  });

  // The same-instance factory shape ran every hook twice under @nestjs/core 11.1.29; only the alias
  // outcome is pinned here, since that is the guarantee the modules above rely on.
  it('runs lifecycle hooks once when the port is a useExisting alias', async () => {
    const PORT = Symbol('PORT');
    const calls = { init: 0, bootstrap: 0, destroy: 0 };

    @Injectable()
    class Hooked implements OnModuleInit, OnApplicationBootstrap, OnModuleDestroy {
      onModuleInit(): void {
        calls.init++;
      }
      onApplicationBootstrap(): void {
        calls.bootstrap++;
      }
      onModuleDestroy(): void {
        calls.destroy++;
      }
    }

    const port: Provider = { provide: PORT, useExisting: Hooked };
    @Module({ providers: [Hooked, port] })
    class Fixture {}
    const app = await Test.createTestingModule({ imports: [Fixture] }).compile();
    await app.init();
    expect(app.get(PORT)).toBe(app.get(Hooked));
    await app.close();

    expect(calls).toEqual({ init: 1, bootstrap: 1, destroy: 1 });
  });
});
