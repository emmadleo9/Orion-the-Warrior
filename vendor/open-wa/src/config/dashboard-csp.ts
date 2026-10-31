export const DASHBOARD_CSP_NONCE_PLACEHOLDER = '__OPENWA_CSP_NONCE__';

/**
 * Inject the response-specific CSP nonce into the bundled dashboard document.
 *
 * Every occurrence, not just the first: the document carries one placeholder today, in the meta
 * element the plugin config UI reads, but the natural next one is a `nonce=` attribute on a script
 * tag. A single-occurrence replace would leave that one reading the literal placeholder, and the
 * browser would refuse the script with nothing failing server-side.
 */
export function injectDashboardCspNonce(html: string, nonce: string): string {
  return html.split(DASHBOARD_CSP_NONCE_PLACEHOLDER).join(nonce);
}
