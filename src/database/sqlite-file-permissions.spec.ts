// The fs namespace object is frozen, so chmodSync cannot be spyOn'd; wrap it in a mock that
// delegates to the real implementation unless a test overrides one call.
jest.mock('fs', () => {
  const actual = jest.requireActual<typeof import('fs')>('fs');
  return { ...actual, chmodSync: jest.fn(actual.chmodSync) };
});

import * as fs from 'fs';
import { chmodSync, existsSync, mkdtempSync, rmSync, statSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { ConfigService } from '@nestjs/config';
import { SqlitePermissionsBoot, tightenSqliteFilePermissions } from './sqlite-file-permissions';

const modeOf = (path: string): number => statSync(path).mode & 0o777;

describe('tightenSqliteFilePermissions', () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'owa-sqlite-perm-'));
  });
  afterEach(() => {
    chmodSync(dir, 0o755); // a 0o500 test dir must still be cleanable
    rmSync(dir, { recursive: true, force: true });
  });

  it('tightens an existing database file and its WAL/journal sidecars to owner-only', () => {
    const db = join(dir, 'openwa.sqlite');
    writeFileSync(db, '', { mode: 0o644 });
    writeFileSync(`${db}-wal`, '', { mode: 0o644 });
    writeFileSync(`${db}-shm`, '', { mode: 0o644 });
    writeFileSync(`${db}-journal`, '', { mode: 0o644 });

    const tightened = tightenSqliteFilePermissions([db], () => undefined);

    expect(tightened).toEqual([db, `${db}-wal`, `${db}-shm`, `${db}-journal`]);
    for (const path of tightened) expect(modeOf(path)).toBe(0o600);
  });

  it('skips files that do not exist without touching anything', () => {
    expect(tightenSqliteFilePermissions([join(dir, 'absent.sqlite')], () => undefined)).toEqual([]);
    expect(existsSync(join(dir, 'absent.sqlite'))).toBe(false);
  });

  it('is best-effort: an untightenable file warns and does not throw', () => {
    const db = join(dir, 'main.sqlite');
    writeFileSync(db, '', { mode: 0o644 });
    (fs.chmodSync as jest.Mock).mockImplementationOnce(() => {
      throw new Error('EPERM: operation not permitted');
    });

    const warnings: string[] = [];
    expect(() => tightenSqliteFilePermissions([db], m => warnings.push(m))).not.toThrow();

    expect(warnings.length).toBe(1);
    expect(warnings[0]).toContain('main.sqlite');
    expect(warnings[0]).toContain('EPERM');
  });
});

describe('SqlitePermissionsBoot', () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'owa-sqlite-boot-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  const configReturning = (values: Record<string, string>): ConfigService =>
    ({ get: (key: string, defaultValue?: string) => values[key] ?? defaultValue }) as unknown as ConfigService;

  it('tightens both bundled files when the data connection is SQLite', () => {
    const main = join(dir, 'main.sqlite');
    const data = join(dir, 'openwa.sqlite');
    writeFileSync(main, '', { mode: 0o644 });
    writeFileSync(data, '', { mode: 0o644 });
    const boot = new SqlitePermissionsBoot(
      configReturning({ 'database.database': main, 'dataDatabase.type': 'sqlite', 'dataDatabase.database': data }),
    );

    boot.onApplicationBootstrap();

    expect(modeOf(main)).toBe(0o600);
    expect(modeOf(data)).toBe(0o600);
  });

  it('skips the data file when the data connection is Postgres (no local file to tighten)', () => {
    const main = join(dir, 'main.sqlite');
    const data = join(dir, 'should-not-be-touched.sqlite');
    writeFileSync(main, '', { mode: 0o644 });
    writeFileSync(data, '', { mode: 0o644 });
    const boot = new SqlitePermissionsBoot(
      configReturning({ 'database.database': main, 'dataDatabase.type': 'postgres', 'dataDatabase.database': data }),
    );

    boot.onApplicationBootstrap();

    expect(modeOf(main)).toBe(0o600);
    expect(modeOf(data)).toBe(0o644);
  });

  it('falls back to the documented default paths when config supplies none', () => {
    const boot = new SqlitePermissionsBoot(configReturning({}));
    // Must not throw even when neither default file exists (e.g. a fresh checkout before first boot).
    expect(() => boot.onApplicationBootstrap()).not.toThrow();
  });
});
