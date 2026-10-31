import 'reflect-metadata';
import { LoggerService } from '../../common/services/logger.service';
import { DataSource } from 'typeorm';
import { Session } from '../session/entities/session.entity';
import { Webhook } from './entities/webhook.entity';
import { WebhookDeliveryFailure } from './entities/webhook-delivery-failure.entity';
import { WebhookOutboxEvent } from './entities/webhook-outbox-event.entity';
import { WebhookOutboxService } from './webhook-outbox.service';
import { recordWebhookDeliveryFailure } from './utils/record-delivery-failure';

// SQLite serves every repository from one connection, so a transaction a write opens is shared with the
// writes that run while it is open. A re-dispatched key makes open() hit the unique violation it expects.
describe('WebhookOutboxService.open() against a concurrent write (SQLite)', () => {
  let ds: DataSource;

  beforeEach(async () => {
    ds = await new DataSource({
      type: 'better-sqlite3',
      database: ':memory:',
      entities: [Session, Webhook, WebhookDeliveryFailure, WebhookOutboxEvent],
      synchronize: true,
    }).initialize();
  });
  afterEach(() => ds.destroy());

  it('does not undo a delivery failure recorded while a duplicate key is rejected', async () => {
    const outbox = new WebhookOutboxService(ds.getRepository(WebhookOutboxEvent));
    const failures = ds.getRepository(WebhookDeliveryFailure);
    const logger = { error: jest.fn() };
    const lost: number[] = [];

    for (let i = 0; i < 20; i++) {
      const row = { webhookId: 'w1', sessionId: 's1', event: 'message.ack', deliveryId: `d${i}`, payload: { i } };
      await outbox.open({ ...row, idempotencyKey: `ack_${i}` });

      const duplicate = outbox.open({ ...row, idempotencyKey: `ack_${i}`, deliveryId: `d${i}b` });
      const recorded = recordWebhookDeliveryFailure(failures, logger, {
        webhookId: 'w1',
        sessionId: 's1',
        event: 'message.received',
        url: 'https://a.example',
        idempotencyKey: `other_${i}`,
        deliveryId: `x${i}`,
        attempts: 3,
        lastStatusCode: 503,
        lastError: 'HTTP 503',
      });
      const [, result] = await Promise.all([duplicate, recorded]);

      // The recorder answered that the row is durable, so it must be there.
      if (result !== null && (await failures.count({ where: { idempotencyKey: `other_${i}` } })) === 0) lost.push(i);
    }

    expect(lost).toEqual([]);
  });
});

// The payload column is text on SQLite and is parsed when a row is read. A row whose stored text is not
// JSON (an imported or hand-edited row) must cost the sweep that row only, not every row behind it.
describe('WebhookOutboxService.findStale() past an unreadable payload (SQLite)', () => {
  let ds: DataSource;
  let outbox: WebhookOutboxService;

  beforeEach(async () => {
    ds = await new DataSource({
      type: 'better-sqlite3',
      database: ':memory:',
      entities: [Session, Webhook, WebhookDeliveryFailure, WebhookOutboxEvent],
      synchronize: true,
    }).initialize();
    outbox = new WebhookOutboxService(ds.getRepository(WebhookOutboxEvent));
  });
  afterEach(() => ds.destroy());

  const insertRaw = async (id: string, key: string, payload: string, createdAt: string): Promise<void> => {
    await ds.query(
      `INSERT INTO webhook_outbox_events (id, webhookId, sessionId, event, idempotencyKey, deliveryId, payload, state, attempts, createdAt)
       VALUES (?, 'w1', 's1', 'message.received', ?, ?, ?, 'pending', 0, ?)`,
      [id, key, `d-${key}`, payload, createdAt],
    );
  };

  it('returns the readable rows behind it and reports how far it scanned', async () => {
    await insertRaw('00000000-0000-4000-8000-000000000001', 'k1', '{oops', '2026-01-01 00:00:00');
    await insertRaw('00000000-0000-4000-8000-000000000002', 'k2', '{"a":1}', '2026-01-01 00:00:01');
    await insertRaw('00000000-0000-4000-8000-000000000003', 'k3', '{oops', '2026-01-01 00:00:02');

    let scannedThrough: string | undefined;
    const rows = await outbox.findStale(new Date('2026-02-01T00:00:00Z'), 10, undefined, id => (scannedThrough = id));

    expect(rows.map(r => r.idempotencyKey)).toEqual(['k2']);
    expect(rows[0].payload).toEqual({ a: 1 });
    // The cursor passes the unreadable row at the end of the page, or a page of them would be read again forever.
    expect(scannedThrough).toBe('00000000-0000-4000-8000-000000000003');
  });

  it('logs each unreadable row with its id and action as fields, not as the trace', async () => {
    const error = jest.spyOn(LoggerService.prototype, 'error').mockImplementation(() => undefined);
    try {
      await insertRaw('00000000-0000-4000-8000-000000000001', 'k1', '{oops', '2026-01-01 00:00:00');

      await outbox.findStale(new Date('2026-02-01T00:00:00Z'), 10);

      expect(error).toHaveBeenCalledWith(
        expect.stringContaining('could not be read'),
        expect.any(String),
        expect.objectContaining({
          id: '00000000-0000-4000-8000-000000000001',
          action: 'webhook_outbox_row_unreadable',
        }),
      );
    } finally {
      error.mockRestore();
    }
  });
});
