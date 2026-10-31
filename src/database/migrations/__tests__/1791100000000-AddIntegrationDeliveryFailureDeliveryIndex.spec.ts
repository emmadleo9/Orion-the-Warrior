import { DataSource } from 'typeorm';
import { AddIntegrationFabric1781900000000 } from '../1781900000000-AddIntegrationFabric';
import { AddIntegrationDeliveryFailureDeliveryIndex1791100000000 } from '../1791100000000-AddIntegrationDeliveryFailureDeliveryIndex';

const INDEX = 'IDX_integration_delivery_failures_instance_delivery';

describe('AddIntegrationDeliveryFailureDeliveryIndex migration', () => {
  let ds: DataSource;

  beforeEach(async () => {
    ds = new DataSource({ type: 'better-sqlite3', database: ':memory:' });
    await ds.initialize();
    const runner = ds.createQueryRunner();
    await new AddIntegrationFabric1781900000000().up(runner);
    await runner.release();
    // One instance holding many dead letters, which is the shape that made the guards scan.
    const rows: string[] = [];
    for (let i = 0; i < 200; i++) {
      rows.push(`('id${i}', 'inbound', 'plug', 'inst', 'd${i}', 1, 'sandbox 5xx', 0)`);
    }
    await ds.query(
      `INSERT INTO "integration_delivery_failures" ("id","direction","pluginId","instanceId","deliveryId","attempts","lastError","redriven") VALUES ${rows.join(',')}`,
    );
  });

  afterEach(async () => {
    await ds.destroy();
  });

  const indexNames = async (): Promise<string[]> => {
    const rows = await ds.query<{ name: string }[]>(`PRAGMA index_list("integration_delivery_failures")`);
    return rows.map(r => r.name).sort();
  };

  it('creates the per-delivery index next to the instance index', async () => {
    const runner = ds.createQueryRunner();
    await new AddIntegrationDeliveryFailureDeliveryIndex1791100000000().up(runner);

    expect(await indexNames()).toEqual(expect.arrayContaining([INDEX, 'IDX_integration_delivery_failures_instance']));
  });

  it('is idempotent (re-running up is a no-op) and down() drops only its own index', async () => {
    const runner = ds.createQueryRunner();
    const migration = new AddIntegrationDeliveryFailureDeliveryIndex1791100000000();

    await migration.up(runner);
    await expect(migration.up(runner)).resolves.toBeUndefined();
    expect(await indexNames()).toContain(INDEX);

    await migration.down(runner);
    const after = await indexNames();
    expect(after).not.toContain(INDEX);
    expect(after).toContain('IDX_integration_delivery_failures_instance');
  });

  it('the open dead-letter guard is served by the per-delivery index', async () => {
    const runner = ds.createQueryRunner();
    const guard =
      `EXPLAIN QUERY PLAN SELECT COUNT(*) FROM "integration_delivery_failures" ` +
      `WHERE "direction" = 'inbound' AND "pluginId" = 'plug' AND "instanceId" = 'inst' AND "deliveryId" = 'd7' AND "redriven" = 0`;

    // Baseline first: the instance index narrows to the whole instance and the rest is filtered row by
    // row, so the assertion below measures the new index and not a plan that already used deliveryId.
    const before = (await ds.query<{ detail: string }[]>(guard)).map(r => r.detail).join(' ');
    expect(before).toContain('IDX_integration_delivery_failures_instance');
    expect(before).not.toContain('deliveryId=?');

    await new AddIntegrationDeliveryFailureDeliveryIndex1791100000000().up(runner);

    const after = (await ds.query<{ detail: string }[]>(guard)).map(r => r.detail).join(' ');
    expect(after).toContain(INDEX);
    expect(after).toContain('deliveryId=?');
  });
});
