import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * `sharp` must never be imported eagerly here.
 *
 * It is a native module that fails to build or load on some CPUs and stripped images, and it backs
 * exactly one Baileys route: sticker WebP conversion. This file is pulled in by the built-in engine
 * chain that boots unconditionally on BOTH engines, so a top-level `import sharp from 'sharp'` made
 * one optional capability a hard boot requirement for the whole gateway. An operator whose sharp
 * cannot load lost everything, not just sticker sends.
 *
 * The import is now deferred into the one function that uses it, so an unusable sharp degrades that
 * route with a clear error and the gateway still boots. This test locks that: a future edit that
 * re-adds an eager import would silently reinstate the boot dependency.
 */
describe('sharp is imported lazily, not at module load', () => {
  const source = readFileSync(join(__dirname, 'baileys-messaging.ts'), 'utf8');

  // Strip line and block comments so a `sharp` mentioned in prose does not trip the scan.
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

  it('has no top-level static import of sharp', () => {
    const eager = /^\s*import\s+[^;]*\bfrom\s+['"]sharp['"]/m.test(code);
    expect(eager).toBe(false);
  });

  it('defers sharp behind a dynamic import', () => {
    expect(code).toMatch(/await import\(['"]sharp['"]\)/);
  });
});
