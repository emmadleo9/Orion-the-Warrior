/* istanbul ignore file -- PG-gated: only runs under DATABASE_TYPE=postgres (test-postgres CI job);
   skipped in the default test job, so its lines would be unread and skew the global coverage gate. */
import 'reflect-metadata';
import { DataSource, DataSourceOptions } from 'typeorm';
import { join } from 'path';

/**
 * Entity metadata builds a PostgreSQL schema (synchronize gate).
 *
 * Raw SQL that TypeORM passes through VERBATIM is not checked by any other suite. A partial index
 * predicate is the case that bit: `@Index(name, { where: 'mediaPath IS NOT NULL' })` reaches the
 * server unquoted, PostgreSQL folds the bare identifier to lower case, and CREATE INDEX fails with
 * `column "mediapath" does not exist`. Quoting the column in the predicate is the fix.
 *
 * Nothing caught it. The migration-chain suites run on better-sqlite3, which does not case-fold, so
 * they pass either way. The drift gate (migration-drift.spec.ts) cannot see it either, in any
 * dialect: TypeORM's schema differ does not compare predicate TEXT, so an unquoted `where` reports
 * zero drift against a chain-built schema that carries the quoted one. Verified against postgres:16,
 * both forms report the same (empty) mediaPath drift.
 *
 * This suite closes that gap the only way that actually fails: it runs synchronize itself. The
 * entity set is the whole `data` connection rather than Message alone, so any future entity that
 * embeds an unquoted identifier in raw SQL fails here too, not just the one that prompted it.
 *
 * Deployments never take this path. app.module.ts leaves the Postgres data connection on
 * migrations, and env.validation.ts rejects DATABASE_SYNCHRONIZE=true with DATABASE_TYPE=postgres
 * outright. What breaks is any DataSource built on these entities with synchronize enabled, which
 * is the natural shape for a Postgres harness written against the real entities.
 *
 * Runs on its OWN database: synchronize builds a schema from entity metadata, which must not land
 * on the migration-built database the sibling PG specs share.
 */
const POSTGRES_ENABLED = process.env.DATABASE_TYPE === 'postgres';

/** Named for the suite so a crashed run leaves an obvious orphan rather than a mystery database. */
const SCRATCH_DB = 'openwa_entity_synchronize_probe';

const repoRoot = join(__dirname, '../../../..');

/** The `data` connection's entity set, mirroring app.module.ts and data-source.ts. */
const dataEntities = [
  join(repoRoot, 'src/modules/session/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/webhook/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/message/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/template/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/engine/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/integration/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/status-store/**/*.entity{.ts,.js}'),
  join(repoRoot, 'src/modules/automation/**/*.entity{.ts,.js}'),
];

const connection = (database: string): DataSourceOptions => ({
  type: 'postgres',
  host: process.env.DATABASE_HOST || 'localhost',
  port: Number(process.env.DATABASE_PORT || 5432),
  username: process.env.DATABASE_USERNAME || 'openwa',
  password: process.env.DATABASE_PASSWORD || 'openwa',
  database,
});

(POSTGRES_ENABLED ? describe : describe.skip)('data entities synchronize onto PostgreSQL', () => {
  let admin: DataSource;
  let scratch: DataSource | undefined;

  beforeAll(async () => {
    admin = new DataSource(connection(process.env.DATABASE_NAME || 'openwa'));
    await admin.initialize();
    // CREATE/DROP DATABASE cannot run inside a transaction, so they are issued on the admin
    // connection rather than through a query runner.
    await admin.query(`DROP DATABASE IF EXISTS "${SCRATCH_DB}"`);
    await admin.query(`CREATE DATABASE "${SCRATCH_DB}"`);
  }, 60_000);

  afterAll(async () => {
    await scratch?.destroy().catch(() => undefined);
    await admin?.query(`DROP DATABASE IF EXISTS "${SCRATCH_DB}"`).catch(() => undefined);
    await admin?.destroy().catch(() => undefined);
  });

  it('builds the whole schema, quoting the mediaPath partial index predicate', async () => {
    scratch = new DataSource({ ...connection(SCRATCH_DB), entities: dataEntities, synchronize: true });

    // The assertion IS initialize(): an unquoted identifier in any entity's raw SQL rejects here
    // with `column "<folded name>" does not exist` before a single expect() runs.
    await scratch.initialize();

    const indexes = await scratch.query<{ indexdef: string }[]>(
      `SELECT indexdef FROM pg_indexes WHERE indexname = 'IDX_messages_mediaPath'`,
    );

    // Read back from the catalog, not from the entity: this is what the server actually stored, and
    // it is the form the migration that owns the same index name produces.
    expect(indexes).toHaveLength(1);
    expect(indexes[0].indexdef).toContain('WHERE ("mediaPath" IS NOT NULL)');
  }, 120_000);
});
