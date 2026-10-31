import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DataSource } from 'typeorm';
import { WebhookDeliveryFailure } from '../modules/webhook/entities/webhook-delivery-failure.entity';
import { createBootDataSource } from './pg-boot-migrations';

describe('SQLite synchronize upgrades with legacy terminal failures', () => {
  it.each([false, true])(
    'normalizes duplicates before creating the unique index (payload column=%s)',
    async hasPayload => {
      const directory = await mkdtemp(join(tmpdir(), 'openwa-failure-upgrade-'));
      const options = {
        type: 'better-sqlite3' as const,
        database: join(directory, 'data.sqlite'),
        entities: [WebhookDeliveryFailure],
        synchronize: true,
      };
      let ds: DataSource | undefined;
      try {
        ds = await new DataSource(options).initialize();
        await ds.query('DROP INDEX "UQ_webhook_delivery_failures_terminal"');
        const row = {
          webhookId: 'w',
          sessionId: 's1',
          event: 'message.received',
          url: 'https://receiver.example',
          idempotencyKey: 'k',
          attempts: 5,
          lastError: 'HTTP 503',
          createdAt: new Date('2026-10-05'),
        };
        await ds.getRepository(WebhookDeliveryFailure).save([
          { ...row, id: 'a' },
          { ...row, id: 'b', attempts: 3, payload: { body: 'retained' } },
          { ...row, id: 'c', attempts: 0 },
          { ...row, id: 'd', idempotencyKey: undefined },
          { ...row, id: 'e', idempotencyKey: undefined },
        ]);
        if (!hasPayload) await ds.query('ALTER TABLE webhook_delivery_failures DROP COLUMN payload');
        await ds.destroy();
        ds = await createBootDataSource(options);
        if (!ds.isInitialized) await ds.initialize();
        const repository = ds.getRepository(WebhookDeliveryFailure);
        expect((await repository.find({ order: { id: 'ASC' } })).map(failure => failure.id)).toEqual([
          hasPayload ? 'b' : 'a',
          'c',
          'd',
          'e',
        ]);
        await expect(repository.insert({ ...row, id: 'f' })).rejects.toThrow(/UNIQUE constraint failed/);
      } finally {
        if (ds?.isInitialized) await ds.destroy();
        await rm(directory, { recursive: true, force: true });
      }
    },
  );
});
