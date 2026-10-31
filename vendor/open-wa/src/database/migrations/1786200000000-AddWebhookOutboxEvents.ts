import { MigrationInterface, QueryRunner } from 'typeorm';

/**
 * Creates `webhook_outbox_events` - the durable record of an outbound delivery, written before the
 * attempt so a hard crash between persisting a message and completing its POST leaves something
 * behind to replay. Mirrors `ingress_events` on the inbound side, including the retired-payload
 * rule: only a 'pending' row carries a payload, so a dispatched or failed row costs a few columns.
 *
 * UNIQUE(webhookId, idempotencyKey) is the natural key: the key is already salted per webhook at
 * dispatch, so the pair names one delivery exactly and a replay reuses the STORED key.
 *
 * Hand-authored because `synchronize` is off on the `data` connection for Postgres. `payload` is
 * `text` on BOTH dialects to match `jsonColumnType()`, which resolves to 'simple-json' everywhere:
 * a `jsonb` column would be auto-parsed by the pg driver and hand back a shape the entity does not
 * expect.
 */
export class AddWebhookOutboxEvents1786200000000 implements MigrationInterface {
  name = 'AddWebhookOutboxEvents1786200000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    if (await queryRunner.hasTable('webhook_outbox_events')) return;
    const isPostgres = queryRunner.connection.options.type === 'postgres';
    const id = isPostgres
      ? `"id" varchar PRIMARY KEY NOT NULL DEFAULT gen_random_uuid()::varchar`
      : `"id" varchar PRIMARY KEY NOT NULL`;
    // The two date columns are NOT the same type, because they carry different decorators.
    // `lastAttemptAt` is `dateColumnType()` + DateTransformer, which is `text` on SQLite;
    // `createdAt` is a plain @CreateDateColumn, which TypeORM emits as `datetime` there. The drift
    // gate compares the chain against that metadata, so guessing one type for both fails.
    const nullableTs = isPostgres ? 'timestamp' : 'text';
    const createdTs = isPostgres ? 'timestamp' : 'datetime';
    const now = isPostgres ? 'NOW()' : `(datetime('now'))`;

    await queryRunner.query(
      `CREATE TABLE "webhook_outbox_events" (${id}, "webhookId" varchar NOT NULL, "sessionId" varchar NOT NULL, ` +
        `"event" varchar NOT NULL, "idempotencyKey" varchar NOT NULL, "deliveryId" varchar NOT NULL, ` +
        `"payload" text, "state" varchar, "attempts" integer NOT NULL DEFAULT (0), "lastAttemptAt" ${nullableTs}, ` +
        `"createdAt" ${createdTs} NOT NULL DEFAULT ${now})`,
    );

    await queryRunner.query(
      `CREATE UNIQUE INDEX "UQ_webhook_outbox_events_webhook_key" ON "webhook_outbox_events" ("webhookId", "idempotencyKey")`,
    );
    await queryRunner.query(
      `CREATE INDEX "IDX_webhook_outbox_events_state_createdAt" ON "webhook_outbox_events" ("state", "createdAt")`,
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // IF EXISTS so revert is idempotent on a synchronize-bootstrapped DB, where up() took the
    // hasTable early return and the named indexes were never created.
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_webhook_outbox_events_state_createdAt"`);
    await queryRunner.query(`DROP INDEX IF EXISTS "UQ_webhook_outbox_events_webhook_key"`);
    await queryRunner.query(`DROP TABLE IF EXISTS "webhook_outbox_events"`);
  }
}
