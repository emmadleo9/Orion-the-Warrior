/**
 * Jest-only boundary for Puppeteer 25, whose public entry point is ESM.
 *
 * whatsapp-web.js requires Puppeteer eagerly even when a unit test never launches a browser. Jest runs
 * this repository's TypeScript suites as CommonJS, so parsing Puppeteer's ESM entry point would fail
 * before those tests can install their Client.initialize spies. A throwing launch keeps that boundary
 * explicit: a test that accidentally reaches the real browser path must opt into an integration setup.
 */
export function launch(): Promise<never> {
  return Promise.reject(new Error('The Jest Puppeteer mock cannot launch a browser; use an integration test instead.'));
}
