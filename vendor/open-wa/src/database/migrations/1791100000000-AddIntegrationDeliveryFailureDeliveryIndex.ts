import { MigrationInterface, QueryRunner } from 'typeorm';

/**
 * Composite index on `integration_delivery_failures (pluginId, instanceId, deliveryId)`, backing the
 * per-delivery guards of the ingress reconciler (the open dead-letter count, the lowest-id tie-break and
 * the retire update) and of the ingress processor. The only index was (pluginId, instanceId), so each
 * guard read every dead letter of the instance: the cost grew with the dead-letter queue, made the
 * retention hand-off quadratic, and on SQLite ran on the event loop.
 *
 * Hand-authored because `synchronize` is off for the data connection on PostgreSQL (and optional on
 * SQLite). The explicit name matches the entity's @Index, so the synchronize and migration schema paths
 * converge on one index. Idempotent via IF NOT EXISTS (supported by both dialects). The earlier
 * (pluginId, instanceId) index stays: it is a prefix of this one, and dropping it is not worth the risk.
 */
export class AddIntegrationDeliveryFailureDeliveryIndex1791100000000 implements MigrationInterface {
  name = 'AddIntegrationDeliveryFailureDeliveryIndex1791100000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Boot and CLI migrations run on a pool without the runtime statement_timeout (pg-boot-migrations.ts),
    // and MigrationExecutor wraps a lone pending migration in its own transaction, so lift any role- or
    // database-level default for this transaction only, exactly like AddWebhookDeliveryFailureLookupIndex.
    if (queryRunner.dataSource.options.type === 'postgres') {
      await queryRunner.query('SET LOCAL statement_timeout = 0');
    }
    await queryRunner.query(
      `CREATE INDEX IF NOT EXISTS "IDX_integration_delivery_failures_instance_delivery" ON "integration_delivery_failures" ("pluginId", "instanceId", "deliveryId")`,
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS "IDX_integration_delivery_failures_instance_delivery"`);
  }
}
