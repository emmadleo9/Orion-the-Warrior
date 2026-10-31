import { readdirSync, rmSync, statSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

/**
 * Remove the throwaway state roots the lane creates.
 *
 * Every suite gets its own root (setupFiles runs once per test file), so a run leaves one directory
 * per suite behind. Nothing removed them before and the temp dir accumulated hundreds of entries.
 * Anything older than an hour is swept rather than only this run's roots: a killed run leaves its
 * own litter, and the age bound keeps this from deleting a root a concurrent run is still using.
 */
const MAX_AGE_MS = 60 * 60 * 1000;

export default function teardown(): void {
  const root = tmpdir();
  const cutoff = Date.now() - MAX_AGE_MS;
  let entries: string[];
  try {
    entries = readdirSync(root).filter(name => name.startsWith('openwa-e2e-'));
  } catch {
    return;
  }
  for (const name of entries) {
    const target = join(root, name);
    try {
      if (statSync(target).mtimeMs < cutoff) rmSync(target, { force: true, recursive: true });
    } catch {
      // A root the OS or another run removed underneath us is already the outcome we wanted.
    }
  }
}
