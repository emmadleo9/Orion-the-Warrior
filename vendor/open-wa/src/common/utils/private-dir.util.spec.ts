import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { ensurePrivateDir } from './private-dir.util';

// Session credential directories (whatsapp-web.js profiles, baileys creds.json) hold everything
// needed to take over the linked WhatsApp account — read access to the volume must not be enough.
// The plugin registry already writes itself owner-only (plugin-storage.service); these tests pin
// the same guarantee for dirs created on the engine path.
describe('ensurePrivateDir', () => {
  let tmpRoot: string;

  beforeEach(() => {
    tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'private-dir-'));
  });
  afterEach(() => {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it('creates a fresh nested directory with owner-only permissions (0o700)', () => {
    const dir = path.join(tmpRoot, 'baileys', 'alice');

    ensurePrivateDir(dir);

    expect(fs.existsSync(dir)).toBe(true);
    expect(fs.statSync(dir).mode & 0o777).toBe(0o700);
  });

  it('tightens a pre-existing world-readable directory back to 0o700', () => {
    // mkdir's `mode` only applies to directories it creates; an upgraded deployment reuses the
    // session dir it already has, so the re-chmod half is what protects existing installs.
    const dir = path.join(tmpRoot, 'sessions', 'session-alice');
    fs.mkdirSync(dir, { recursive: true, mode: 0o755 });

    ensurePrivateDir(dir);

    expect(fs.statSync(dir).mode & 0o777).toBe(0o700);
  });

  it('is best-effort: an unwritable location must not throw (the engine lib owns real failures)', () => {
    const file = path.join(tmpRoot, 'blocker');
    fs.writeFileSync(file, 'not a directory');

    expect(() => ensurePrivateDir(path.join(file, 'under-a-file'))).not.toThrow();
  });
});
