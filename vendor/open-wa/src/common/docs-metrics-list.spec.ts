import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * `docs/10-devops-infrastructure.md` introduces its metric table with "the complete set — nothing
 * else is emitted". That is a claim about ABSENCE, and nothing bound it to the renderer: every
 * metric added after the table was written kept the claim green while making it false. It had
 * drifted to listing 10 of the 15 series `MetricsService` actually emits.
 *
 * An operator reads that table to decide what to alert on, so a missing row is not cosmetic — it is
 * a signal nobody knows exists.
 *
 * This gate compares the table against the renderer's own emission sites. A metric added to the
 * service without a row, a row left behind after the service stops emitting it, or a Type column
 * that disagrees with the `# TYPE` line all fail here.
 */
describe('docs/10 metric table matches MetricsService', () => {
  const read = (...parts: string[]): string => readFileSync(join(__dirname, '..', '..', ...parts), 'utf8');

  /**
   * Files whose lines end up in one scrape. `render()` composes its output from helpers in other
   * modules, so scanning the service alone missed the unprefixed HTTP RED series entirely — and a
   * gate that cannot see a series cannot bind it.
   */
  const RENDER_SOURCES = [
    ['src', 'modules', 'metrics', 'metrics.service.ts'],
    ['src', 'common', 'metrics', 'request-metrics.ts'],
  ];

  /**
   * Emitted series, read from the two forms the renderers use:
   *   - `gauge('name', …)` — the helper pushes HELP/TYPE/value, always a gauge.
   *   - `# TYPE name counter|gauge` — the hand-written blocks.
   * Deliberately NOT restricted to the `openwa_` prefix: two series are conventionally unprefixed so
   * generic RED dashboards match them, and a prefix filter is exactly how they escaped this gate.
   */
  const emitted = (): Map<string, string> => {
    const found = new Map<string, string>();
    for (const parts of RENDER_SOURCES) {
      const source = read(...parts);
      for (const [, name] of source.matchAll(/\bgauge\(\s*'([a-z][a-z0-9_]*)'/g)) {
        found.set(name, 'gauge');
      }
      for (const [, name, type] of source.matchAll(/# TYPE ([a-z][a-z0-9_]*) (gauge|counter|histogram)/g)) {
        found.set(name, type);
      }
    }
    return found;
  };

  /**
   * The composition itself. RENDER_SOURCES is a hand-kept list, and a third helper spliced into
   * `render()` would escape this gate the same way the HTTP series did — silently, because the
   * comparison would still pass on the files it does know. Every `...renderX()` splice must resolve
   * to a module this spec reads.
   */
  it('reads every module whose lines render() splices in', () => {
    const service = read('src', 'modules', 'metrics', 'metrics.service.ts');
    const splices = [...service.matchAll(/lines\.push\(\.\.\.(\w+)\(/g)].map(m => m[1]);
    expect(splices.length).toBeGreaterThan(0); // control: the pattern must match something

    const scanned = RENDER_SOURCES.map(parts => read(...parts)).join('\n');
    for (const helper of splices) {
      expect(scanned).toContain(`export function ${helper}`);
    }
  });

  /** The table rows: `| \`openwa_x\` | type | labels | meaning |`. */
  const documented = (): Map<string, string> => {
    const doc = read('docs', '10-devops-infrastructure.md');
    const start = doc.indexOf('**Exported metric names**');
    expect(start).toBeGreaterThan(-1);
    const table = doc.slice(start);
    const rows = new Map<string, string>();
    for (const line of table.split('\n')) {
      if (!line.startsWith('|')) {
        if (rows.size > 0) break; // past the table
        continue;
      }
      const cells = line.split('|').map(cell => cell.trim());
      const name = cells[1]?.match(/^`([a-z][a-z0-9_]*)`$/)?.[1];
      if (name) rows.set(name, cells[2]);
    }
    return rows;
  };

  // Positive control. Both readers are regex-based, and a regex that matches nothing would make
  // every comparison below pass vacuously — two empty sets are equal. Fail loudly instead.
  it('both readers actually read something', () => {
    expect(emitted().size).toBeGreaterThanOrEqual(10);
    expect(emitted().get('openwa_up')).toBe('gauge');
    expect(documented().size).toBeGreaterThanOrEqual(10);
    expect(documented().get('openwa_up')).toBe('gauge');
  });

  it('lists exactly the series the renderer emits', () => {
    expect([...documented().keys()].sort()).toEqual([...emitted().keys()].sort());
  });

  it('gives each series the type the renderer declares', () => {
    expect(Object.fromEntries([...documented()].sort())).toEqual(Object.fromEntries([...emitted()].sort()));
  });
});
