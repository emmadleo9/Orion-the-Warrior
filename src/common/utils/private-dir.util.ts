import * as fs from 'fs';

/**
 * Create `dir` (with parents) owner-only, or tighten a pre-existing one to 0o700. Both halves are
 * needed: mkdir's `mode` applies only to directories it actually creates, so a directory that
 * already exists (an upgraded deployment reusing its session dir) keeps its old mode unless
 * chmod'd explicitly.
 *
 * Best-effort by design: callers run ahead of an engine library that creates the directory itself
 * and fails loudly when the location is genuinely unusable — a permissions-hardening failure here
 * (odd filesystem rejecting chmod, exotic mounts) must not take the session down instead.
 */
export function ensurePrivateDir(dir: string): void {
  try {
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    fs.chmodSync(dir, 0o700);
  } catch {
    /* best-effort hardening — the engine library creates/uses the directory regardless */
  }
}
