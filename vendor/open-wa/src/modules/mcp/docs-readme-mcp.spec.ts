import * as fs from 'fs';
import * as path from 'path';
import { resolveMcpReadOnly } from './mcp.server';

/**
 * README described the MCP surface as write-enabled by default and never mentioned the knob that
 * enables it. `resolveMcpReadOnly` defaults to READ-ONLY unless `MCP_READONLY` is the literal
 * string 'false' — the secure default a code comment says was deliberately chosen — so an operator
 * following README wired a client, saw no send/reply/group tools, and had nothing in README to point
 * them at. In the other direction it misstated the shipped security posture.
 *
 * The counts are derived from the tool sources here, so a tier change fails this instead of quietly
 * making the prose wrong again.
 */
const repoRoot = path.join(__dirname, '..', '..', '..');
const readme = fs.readFileSync(path.join(repoRoot, 'README.md'), 'utf8');

function tierCounts(): { read: number; write: number } {
  const dir = path.join(repoRoot, 'src', 'core', 'agent-tools', 'tools');
  let read = 0;
  let write = 0;
  for (const file of fs.readdirSync(dir).filter(f => f.endsWith('.tools.ts'))) {
    const src = fs.readFileSync(path.join(dir, file), 'utf8');
    read += (src.match(/tier:\s*'read'/g) ?? []).length;
    write += (src.match(/tier:\s*'write'/g) ?? []).length;
  }
  return { read, write };
}

describe('README describes the MCP surface the code actually mounts', () => {
  // Guards the counts below: an extractor that matched nothing would make every assertion vacuous.
  it('counts both tiers from the tool sources', () => {
    const { read, write } = tierCounts();
    expect(read).toBeGreaterThan(0);
    expect(write).toBeGreaterThan(0);
  });

  it('mounts read-only unless MCP_READONLY is explicitly "false"', () => {
    const prev = process.env.MCP_READONLY;
    try {
      delete process.env.MCP_READONLY;
      expect(resolveMcpReadOnly()).toBe(true);
      process.env.MCP_READONLY = 'true';
      expect(resolveMcpReadOnly()).toBe(true);
      process.env.MCP_READONLY = 'false';
      expect(resolveMcpReadOnly()).toBe(false);
    } finally {
      if (prev === undefined) delete process.env.MCP_READONLY;
      else process.env.MCP_READONLY = prev;
    }
  });

  it('states the DEFAULT tool count, not just the total', () => {
    const { read } = tierCounts();
    expect(readme).toContain(`${read} read-only tools`);
  });

  it('names the knob that unlocks the write tier', () => {
    const { read, write } = tierCounts();
    expect(readme).toContain('MCP_READONLY=false');
    expect(readme).toContain(`${read + write} tools`);
  });
});
