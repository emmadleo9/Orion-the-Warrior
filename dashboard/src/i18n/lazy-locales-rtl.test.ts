// The first load of a non-English, right-to-left visitor — the path where the lazy split actually
// costs something, because the catalogue is now a network round trip that first paint waits on.
// `lazy-locales.test.ts` cannot cover it: the i18n module is a singleton, so one process only ever
// has one initial language, and there it is English. Detection is steered the way a returning
// visitor steers it, through the `openwa_language` key the detector caches into, which also
// exercises the localStorage branch of `detection.order` that nothing else reaches.
//
// Runner constraints honored here: loader hooks registered before any app-module import (see
// test-helpers/register-hooks), and JSDOM installed before the module is imported — both because it
// reads `document` and `localStorage` while initializing, and because the seeded key has to be in
// place before detection runs.
import '../test-helpers/register-hooks.ts';
import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import type { installJsdomGlobals as installJsdomGlobalsFn } from '../test-helpers/jsdom.ts';

type I18nModule = typeof import('./index.ts');

let i18n: I18nModule['default'];

before(async () => {
  const { installJsdomGlobals } = (await import('../test-helpers/jsdom.ts')) as {
    installJsdomGlobals: typeof installJsdomGlobalsFn;
  };
  await installJsdomGlobals();
  localStorage.setItem('openwa_language', 'ar');
  const module = (await import('./index.ts')) as I18nModule;
  i18n = module.default;
  await module.i18nReady;
});

test('a stored Arabic preference is detected and its catalogue is loaded before i18nReady settles', () => {
  assert.equal(i18n.resolvedLanguage, 'ar', 'the stored preference was not detected');
  assert.equal(i18n.t('sessionStatus.failed'), 'فشل', 'the catalogue had not arrived when the promise settled');
});

// Rendering waits on the same promise, so this is the state the document is in at first paint —
// the reason the split does not show a left-to-right frame before flipping.
test('the document is already right-to-left when i18nReady settles', () => {
  assert.equal(document.documentElement.dir, 'rtl');
  assert.equal(document.documentElement.lang, 'ar');
});

// A non-English visitor fetches two catalogues, not one: `fallbackLng` keeps English resident so a
// key that a translation happens to be missing still renders as copy rather than as a raw key. The
// published byte figures for this change count both, which makes the second fetch part of what was
// promised rather than an implementation detail. Only a non-English initial language can assert it —
// when English is the detected language, it is resident whether or not anything falls back to it.
test('the English fallback is fetched alongside the detected catalogue', () => {
  assert.ok(i18n.hasResourceBundle('ar', 'translation'), 'the detected catalogue is not loaded');
  assert.ok(i18n.hasResourceBundle('en', 'translation'), 'the English fallback was not fetched');
});
