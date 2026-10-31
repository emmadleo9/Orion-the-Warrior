// Everything the lazy locale split can break is runtime behaviour no build gate can see: the active
// catalogue has to be in place before anything renders, a language switch has to pull its catalogue
// in before components re-read it, and the direction flip that dresses Hebrew and Arabic has to
// survive both. Exercised against the real i18n module under the same JSDOM bootstrap the page
// render tests use, because the loader only exists at runtime — `locales.test.ts` deliberately reads
// this module as text and so can say nothing about any of it.
//
// Runner constraints honored here: loader hooks registered before any app-module import (see
// test-helpers/register-hooks), and JSDOM installed before importing a module that touches
// `document` and `localStorage` while it initializes.
import '../test-helpers/register-hooks.ts';
import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import type { installJsdomGlobals as installJsdomGlobalsFn } from '../test-helpers/jsdom.ts';

type I18nModule = typeof import('./index.ts');

let i18n: I18nModule['default'];

before(async () => {
  const { installJsdomGlobals } = (await import('../test-helpers/jsdom.ts')) as {
    installJsdomGlobals: typeof installJsdomGlobalsFn;
  };
  await installJsdomGlobals();
  const module = (await import('./index.ts')) as I18nModule;
  i18n = module.default;
  await module.i18nReady;
});

// If the catalogue were still in flight when this settles, `t` would hand back the raw key and the
// shell would paint it before swapping in real copy a tick later.
test('the detected catalogue is loaded by the time i18nReady settles', () => {
  assert.equal(i18n.t('sessionStatus.failed'), 'Failed');
  assert.equal(document.documentElement.lang, 'en');
  assert.equal(document.documentElement.dir, 'ltr');
});

// The whole reason the loader is an i18next backend rather than a hand-rolled fetch: i18next holds
// `languageChanged` until the catalogue has arrived. Reading the Arabic copy straight after the
// await is what proves that ordering — a half-loaded switch would answer with the English fallback.
test('switching language at runtime loads that catalogue before it resolves', async () => {
  await i18n.changeLanguage('ar');
  assert.equal(i18n.t('sessionStatus.failed'), 'فشل');

  await i18n.changeLanguage('de');
  assert.equal(i18n.t('sessionStatus.failed'), 'Fehlgeschlagen');
});

test('direction follows the language in both directions, for both RTL locales', async () => {
  await i18n.changeLanguage('he');
  assert.equal(document.documentElement.dir, 'rtl');
  assert.equal(document.documentElement.lang, 'he');

  await i18n.changeLanguage('ar');
  assert.equal(document.documentElement.dir, 'rtl');

  // Back to an LTR language: a direction that only ever gets set is a direction that sticks.
  await i18n.changeLanguage('en');
  assert.equal(document.documentElement.dir, 'ltr');
  assert.equal(document.documentElement.lang, 'en');
});

// A catalogue that fails to arrive is the one state these runtime tests cannot reach: the loader
// reads real files here, so it always succeeds. In a browser it can 404 — a tab left open across a
// redeploy asks for a hashed chunk that no longer exists — and i18next answers by setting
// `language` to the request, emitting `languageChanged`, and serving the English fallback from
// `t()`. Direction therefore has to follow `resolvedLanguage`, which reports what actually answered,
// or the document is dressed right-to-left around English copy. Asserted against the source for the
// same reason the main.tsx gate below is: the wiring is what breaks, and it cannot be provoked here.
test('direction follows the catalogue that answered, not the one that was asked for', () => {
  const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'index.ts'), 'utf8');
  const body = source.slice(source.indexOf('function applyDirection'));
  // Bound to the assignment rather than to the mere presence of the call, so a leftover reference to
  // resolvedLanguage cannot satisfy this while the value actually used comes from somewhere else.
  assert.match(
    body.slice(0, body.indexOf('}')),
    /const resolved = resolveSupportedLanguage\(\s*i18n\.resolvedLanguage\b/,
    'applyDirection no longer derives the direction it applies from i18n.resolvedLanguage',
  );
});

// The catalogue is fetched now instead of bundled, so first paint is only free of untranslated text
// while the entry keeps rendering behind that promise. Nothing in a build or a type check notices
// if the gate is dropped, and the flash it brings back is a tick long — easy to miss by hand.
test('main.tsx renders behind i18nReady', () => {
  const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'main.tsx'), 'utf8');
  // Comments stripped first: this file explains the deferral at length, and a gate that reads prose
  // fires on a description of the bug as readily as on the bug. Counting the calls is what closes
  // the gap an anchored pattern leaves — an unguarded render put anywhere but column zero, or added
  // alongside the deferred one, is a second createRoot rather than a differently-shaped first.
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  assert.match(code, /i18nReady\.then\(/, 'main.tsx no longer defers the first render until the catalogue is loaded');
  assert.match(code, /const render = \(\) =>\s*createRoot\(/, 'the deferred render no longer owns the createRoot call');
  assert.equal(
    (code.match(/createRoot\(/g) ?? []).length,
    1,
    'main.tsx mounts more than once — a render that is not the deferred one does not wait for the catalogue',
  );
});
