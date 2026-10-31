'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { mkdtempSync, rmSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');

// Baileys reads the duration of an outgoing audio file with music-metadata's parseFile. In 11.13.0 an
// EBML element declaring a 32 GiB length made that call abort the whole process on a native assertion
// instead of throwing, so one crafted file stopped every session. The parse runs in a child so a
// regression kills the child, not the test runner, and the exit signal can be asserted.
const OVERSIZED_WEBM = Buffer.from(
  [
    '1a45dfa3874282847765626d', // EBML header, DocType "webm"
    '1853806701ffffffffffffff', // Segment, unknown size
    '1549a96601ffffffffffffff', // Info, unknown size
    '7ba9', // Title leaf ...
    '0100000800000000', // ... declaring 32 GiB
    '41', // one byte of content
  ].join(''),
  'hex',
);

test('a WebM leaf that declares 32 GiB is rejected by music-metadata, not fatal to the process', () => {
  const dir = mkdtempSync(join(tmpdir(), 'openwa-mm-'));
  try {
    const file = join(dir, 'oversized.webm');
    writeFileSync(file, OVERSIZED_WEBM);
    const child = spawnSync(
      process.execPath,
      [
        '-e',
        "import('music-metadata').then(mm => mm.parseFile(process.argv[1], { duration: true })).then(() => process.exit(0), () => process.exit(7))",
        file,
      ],
      { cwd: join(__dirname, '..'), encoding: 'utf8' },
    );
    assert.equal(child.signal, null, `the parser killed its process with ${child.signal}: ${child.stderr}`);
    assert.ok([0, 7].includes(child.status), `unexpected exit ${child.status}: ${child.stderr}`);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
