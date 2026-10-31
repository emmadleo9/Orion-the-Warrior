import { assertDownloadSha256, assertPluginInstallUrl, expectedSha256FromUrl } from './plugin-download';
import { createHash } from 'crypto';

/**
 * Optional content integrity for plugin downloads: the expected sha256 travels IN the URL as a
 * `#sha256=` fragment (never sent to the server), and verification is fail-closed whenever the
 * marker is present. Query params — even ones named `sha256`/`checksum` — are NOT markers: they
 * are sent to the server and may belong to the download host's own contract.
 */
describe('expectedSha256FromUrl', () => {
  const digest = 'a'.repeat(64);

  it('extracts the digest from a #sha256= fragment (case-insensitive hex)', () => {
    expect(expectedSha256FromUrl(`https://h/pkg.zip#sha256=${digest}`)).toBe(digest);
    expect(expectedSha256FromUrl(`https://h/pkg.zip#sha256=${digest.toUpperCase()}`)).toBe(digest);
  });

  it('does not seize ?sha256= / ?checksum= query params — they belong to the host, not to OpenWA', () => {
    expect(expectedSha256FromUrl(`https://h/pkg.zip?sha256=${digest}`)).toBeNull();
    expect(expectedSha256FromUrl(`https://h/pkg.zip?checksum=${digest}`)).toBeNull();
    // A host-side checksum param in its own (non-sha256-hex) format must not fail the download.
    expect(expectedSha256FromUrl('https://h/pkg.zip?checksum=1a2b3c4d&dl=1')).toBeNull();
  });

  it('returns null when the URL carries no integrity marker', () => {
    expect(expectedSha256FromUrl('https://h/pkg.zip')).toBeNull();
    expect(expectedSha256FromUrl('https://h/pkg.zip#download')).toBeNull();
    expect(expectedSha256FromUrl('not a url')).toBeNull(); // downstream URL validation rejects it
  });

  it('fails closed on a malformed marker', () => {
    expect(() => expectedSha256FromUrl('https://h/pkg.zip#sha256=xyz')).toThrow(/64-character hex/i);
    expect(() => expectedSha256FromUrl(`https://h/pkg.zip#sha256=${'a'.repeat(63)}`)).toThrow(/64-character hex/i);
  });

  it('honors the fragment alongside unrelated query params (the params are simply ignored)', () => {
    expect(expectedSha256FromUrl(`https://h/pkg.zip?checksum=1a2b3c#sha256=${digest}`)).toBe(digest);
    expect(expectedSha256FromUrl(`https://h/pkg.zip?sha256=${'b'.repeat(64)}#sha256=${digest}`)).toBe(digest);
  });
});

describe('assertDownloadSha256', () => {
  const body = Buffer.from('plugin zip bytes');
  const digest = createHash('sha256').update(body).digest('hex');

  it('is a no-op when the URL carries no integrity marker', () => {
    expect(() => assertDownloadSha256('https://h/pkg.zip', body)).not.toThrow();
  });

  it('passes when the digest matches the downloaded bytes', () => {
    expect(() => assertDownloadSha256(`https://h/pkg.zip#sha256=${digest}`, body)).not.toThrow();
  });

  it('throws when the digest does not match (substituted package)', () => {
    expect(() => assertDownloadSha256(`https://h/pkg.zip#sha256=${'0'.repeat(64)}`, body)).toThrow(/sha256 mismatch/i);
  });
});

describe('assertPluginInstallUrl', () => {
  const digest = 'a'.repeat(64);

  it('accepts https as-is, with or without an integrity pin', () => {
    expect(() => assertPluginInstallUrl('https://h/pkg.zip')).not.toThrow();
    expect(() => assertPluginInstallUrl(`https://h/pkg.zip#sha256=${digest}`)).not.toThrow();
  });

  it('rejects plain http without a content pin — the package is executable code', () => {
    expect(() => assertPluginInstallUrl('http://h/pkg.zip')).toThrow(/#sha256=/);
    // A query-param digest is NOT a pin (it belongs to the download host).
    expect(() => assertPluginInstallUrl(`http://h/pkg.zip?sha256=${digest}`)).toThrow(/#sha256=/);
  });

  it('accepts plain http carrying a well-formed #sha256= pin (verified against the download)', () => {
    expect(() => assertPluginInstallUrl(`http://h/pkg.zip#sha256=${digest}`)).not.toThrow();
    expect(() => assertPluginInstallUrl(`http://h/pkg.zip#sha256=${digest.toUpperCase()}`)).not.toThrow();
  });

  it('fails closed on http with a malformed pin rather than degrading to no verification', () => {
    expect(() => assertPluginInstallUrl('http://h/pkg.zip#sha256=xyz')).toThrow(/64-character hex/i);
  });

  it('leaves unparseable URLs and other schemes to the SSRF guard (no duplicate rejection here)', () => {
    expect(() => assertPluginInstallUrl('not a url')).not.toThrow();
    expect(() => assertPluginInstallUrl('ftp://h/pkg.zip')).not.toThrow();
  });
});

// a URL install EXECUTES third-party code — https authenticates the channel, not the bytes.
// In production (or wherever PLUGIN_INSTALL_REQUIRE_PIN says so) the pin is mandatory.
describe('assertPluginInstallUrl — pin required in production', () => {
  const env = { ...process.env };
  afterEach(() => {
    process.env = { ...env };
  });

  it('rejects an unpinned https URL when NODE_ENV=production', () => {
    process.env.NODE_ENV = 'production';
    delete process.env.PLUGIN_INSTALL_REQUIRE_PIN;
    expect(() => assertPluginInstallUrl('https://release.example.com/pkg.zip')).toThrow(/integrity pin/);
  });

  it('accepts the same URL with a pin', () => {
    process.env.NODE_ENV = 'production';
    expect(() => assertPluginInstallUrl('https://release.example.com/pkg.zip#sha256=' + 'a'.repeat(64))).not.toThrow();
  });

  it('keeps the lighter default outside production', () => {
    process.env.NODE_ENV = 'development';
    delete process.env.PLUGIN_INSTALL_REQUIRE_PIN;
    expect(() => assertPluginInstallUrl('https://release.example.com/pkg.zip')).not.toThrow();
  });

  it('PLUGIN_INSTALL_REQUIRE_PIN=true enforces the pin regardless of NODE_ENV', () => {
    process.env.NODE_ENV = 'development';
    process.env.PLUGIN_INSTALL_REQUIRE_PIN = 'true';
    expect(() => assertPluginInstallUrl('https://release.example.com/pkg.zip')).toThrow(/integrity pin/);
  });

  it('PLUGIN_INSTALL_REQUIRE_PIN=false lifts the requirement even in production (operator opt-out)', () => {
    process.env.NODE_ENV = 'production';
    process.env.PLUGIN_INSTALL_REQUIRE_PIN = 'false';
    expect(() => assertPluginInstallUrl('https://release.example.com/pkg.zip')).not.toThrow();
  });
});
