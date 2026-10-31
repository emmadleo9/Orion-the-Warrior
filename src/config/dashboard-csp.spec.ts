import { DASHBOARD_CSP_NONCE_PLACEHOLDER, injectDashboardCspNonce } from './dashboard-csp';

describe('injectDashboardCspNonce', () => {
  it('keeps each dashboard document nonce isolated (multi-tab safe)', () => {
    const template = `<meta name="openwa-csp-nonce" content="${DASHBOARD_CSP_NONCE_PLACEHOLDER}">`;
    expect(injectDashboardCspNonce(template, 'tab-a')).toContain('content="tab-a"');
    expect(injectDashboardCspNonce(template, 'tab-b')).toContain('content="tab-b"');
  });
});

describe('injectDashboardCspNonce: every occurrence', () => {
  it('substitutes a placeholder that appears more than once', () => {
    const html = `<meta content="${DASHBOARD_CSP_NONCE_PLACEHOLDER}"><script nonce="${DASHBOARD_CSP_NONCE_PLACEHOLDER}">`;
    const out = injectDashboardCspNonce(html, 'abc123');
    // A first-occurrence-only replace leaves the script reading the literal placeholder, which the
    // browser then refuses under the document's own CSP.
    expect(out).toBe('<meta content="abc123"><script nonce="abc123">');
    expect(out).not.toContain(DASHBOARD_CSP_NONCE_PLACEHOLDER);
  });
});
