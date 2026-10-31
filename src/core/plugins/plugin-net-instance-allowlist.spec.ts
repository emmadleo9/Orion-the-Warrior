import { HookManager } from '../hooks';
import { PluginCapabilityContext } from './plugin-capability-context';
import { PluginHostServices } from './plugin-host-services';
import { PluginStorageService } from './plugin-storage.service';
import { PluginInstance as LoadedPlugin, PluginManifest, PluginStatus, PluginType } from './plugin.interfaces';
import { PluginInstance as InstanceRow } from '../../modules/integration/entities/plugin-instance.entity';
import { createLogger } from '../../common/services/logger.service';

/**
 * `net.allowConfigHosts` admits the host of an operator-configured URL so an adapter can reach its
 * tenant without `net.allow: ['*']`. The allowlist was built from the base config plus every
 * scope-keyed override — and provisioning projects an instance's config into that store keyed by
 * SCOPE, so for two instances sharing one scope the store holds whichever was written last.
 *
 * That was survivable only while dispatch handed every instance that same last-written config: the
 * host a plugin was told to call was the host the allowlist had admitted. Now that dispatch hands
 * each instance its OWN config, the other instance is told to call a host the allowlist never saw,
 * and its fetch is refused — the config is right and unusable. Both halves have to agree, so the
 * allowlist reads the instance rows too.
 */
describe('the net allowlist admits every provisioned instance host', () => {
  const PLUGIN_ID = 'chat-adapter';
  const SCOPE = 'session-shared';

  const manifest: PluginManifest = {
    id: PLUGIN_ID,
    name: 'Chat Adapter',
    version: '1.0.0',
    type: PluginType.EXTENSION,
    main: 'index.js',
    permissions: ['net:fetch'],
    net: { allow: [], allowConfigHosts: ['baseUrl'] },
  };

  const row = (instanceId: string, baseUrl: string, enabled = true): InstanceRow => ({
    id: `${PLUGIN_ID}:${instanceId}`,
    pluginId: PLUGIN_ID,
    instanceId,
    sessionScope: SCOPE,
    secret: 's',
    verifyToken: null,
    config: { baseUrl },
    enabled,
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  /** The loaded plugin as the loader holds it: the scope slice carries the LAST projected instance. */
  const loaded = (): LoadedPlugin =>
    ({
      manifest,
      status: PluginStatus.ENABLED,
      config: {},
      sessionConfig: { [SCOPE]: { baseUrl: 'https://tenant-b.invalid' } },
      activeSessions: [SCOPE],
    }) as unknown as LoadedPlugin;

  const netCapability = (instances: InstanceRow[]) => {
    const hostServices = {
      getPluginInstancePort: () => ({ list: () => Promise.resolve(instances) }),
    } as unknown as PluginHostServices;
    const ctx = new PluginCapabilityContext(createLogger('net-allowlist.spec'), hostServices, new HookManager(), {
      createPluginStorage: () => ({}),
    } as unknown as PluginStorageService);
    return ctx.createPluginContext(loaded()).net;
  };

  /** The allowlist refusal is thrown before any socket work, so it is distinguishable by message. */
  const refusalFor = async (net: ReturnType<typeof netCapability>, url: string): Promise<string> => {
    try {
      await net.fetch(url);
      return '(no error)';
    } catch (error) {
      return error instanceof Error ? error.message : String(error);
    }
  };

  it('admits the host of an instance that is not the last one projected onto the scope', async () => {
    const net = netCapability([row('acct-a', 'https://tenant-a.invalid'), row('acct-b', 'https://tenant-b.invalid')]);

    // A .invalid host cannot resolve, so anything that is NOT the allowlist refusal proves the URL
    // cleared the gate and reached the socket — which is the whole claim.
    expect(await refusalFor(net, 'https://tenant-a.invalid/api/x')).not.toMatch(/may not fetch/);
  });

  it('still admits the host the scope slice carries', async () => {
    const net = netCapability([row('acct-a', 'https://tenant-a.invalid'), row('acct-b', 'https://tenant-b.invalid')]);

    expect(await refusalFor(net, 'https://tenant-b.invalid/api/x')).not.toMatch(/may not fetch/);
  });

  // Negative twin: widening the allowlist to the instance rows must not open it to anything else.
  it('still refuses a host no config names', async () => {
    const net = netCapability([row('acct-a', 'https://tenant-a.invalid')]);

    expect(await refusalFor(net, 'https://elsewhere.invalid/api/x')).toMatch(/may not fetch/);
  });

  // A disabled instance is not a tenant the operator is running; its host must not stay admitted.
  it('does not admit a disabled instance host', async () => {
    const net = netCapability([row('acct-a', 'https://tenant-a.invalid', false)]);

    expect(await refusalFor(net, 'https://tenant-a.invalid/api/x')).toMatch(/may not fetch/);
  });

  /**
   * Not every host exposes an instance service, and the store can fail. Neither is a reason to
   * refuse a fetch the base config already allows — the lookup only ever ADDS hosts, so losing it
   * must degrade to the previous allowlist rather than to a denial or a crash.
   */
  it('falls back to the config-derived allowlist when the instance lookup is unavailable', async () => {
    const hostServices = {
      getPluginInstancePort: () => {
        throw new Error('no instance service in this host');
      },
    } as unknown as PluginHostServices;
    const ctx = new PluginCapabilityContext(createLogger('net-allowlist.spec'), hostServices, new HookManager(), {
      createPluginStorage: () => ({}),
    } as unknown as PluginStorageService);
    const net = ctx.createPluginContext(loaded()).net;

    // The scope slice still admits its own host …
    expect(await refusalFor(net, 'https://tenant-b.invalid/api/x')).not.toMatch(/may not fetch/);
    // … and nothing else silently became allowed.
    expect(await refusalFor(net, 'https://elsewhere.invalid/api/x')).toMatch(/may not fetch/);
  });
});
