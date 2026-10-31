import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decideScroll, shouldFetchOlderMessages, type ScrollGeometry } from './scrollDecision.ts';

const at = (scrollTop: number, scrollHeight = 1000, clientHeight = 500): ScrollGeometry => ({
  scrollTop,
  scrollHeight,
  clientHeight,
});

test('outgoing message always scrolls to bottom', () => {
  // User scrolled way up (0).
  assert.equal(decideScroll('outgoing', at(0)), 'bottom');
});

test('incoming message scrolls to bottom when user is near bottom (default 100px)', () => {
  // gap = scrollHeight - scrollTop - clientHeight = 1000 - 450 - 500 = 50 < 100
  assert.equal(decideScroll('incoming', at(450)), 'bottom');
});

test('incoming message preserves position when user is far from bottom', () => {
  // gap = 1000 - 100 - 500 = 400 > 100
  assert.equal(decideScroll('incoming', at(100)), 'preserve');
});

test('incoming message at exact bottom scrolls (gap = 0)', () => {
  // gap = 1000 - 500 - 500 = 0 < 100
  assert.equal(decideScroll('incoming', at(500)), 'bottom');
});

test('incoming message exactly at threshold preserves (gap = 100 is NOT < 100)', () => {
  // gap = 1000 - 400 - 500 = 100, strictly < 100 is false
  assert.equal(decideScroll('incoming', at(400)), 'preserve');
});

test('custom threshold overrides default', () => {
  // gap = 200, threshold 300 → bottom
  assert.equal(decideScroll('incoming', at(300), 300), 'bottom');
});

// --- shouldFetchOlderMessages -------------------------------------------------
// A long thread: 7045px of content in a 148px viewport, the shape measured in the browser.
const longThread = { scrollTop: 20, scrollHeight: 7045, clientHeight: 148 };

test('reading back to the top pulls the next older page', () => {
  assert.equal(
    shouldFetchOlderMessages({ isUserScroll: true, geometry: longThread, hasMore: true, isFetching: false }),
    true,
  );
});

test('the render-time sync call never pages, however close to the top it reports', () => {
  // The regression: the thread's listener also runs on every render to refresh the jump button, and
  // a freshly opened room reports scrollTop 0 there. Paging from it cascaded — each page re-rendered
  // and asked for the next, so opening a chat pulled its whole history in one burst.
  assert.equal(
    shouldFetchOlderMessages({
      isUserScroll: false,
      geometry: { scrollTop: 0, scrollHeight: 7045, clientHeight: 148 },
      hasMore: true,
      isFetching: false,
    }),
    false,
  );
});

test('a thread shorter than its viewport never pages', () => {
  // Same cascade from the other side: it sits at scrollTop 0 permanently.
  assert.equal(
    shouldFetchOlderMessages({
      isUserScroll: true,
      geometry: { scrollTop: 0, scrollHeight: 300, clientHeight: 300 },
      hasMore: true,
      isFetching: false,
    }),
    false,
  );
});

test('a fetch already in flight is not doubled', () => {
  // Scroll events arrive per frame, so one gesture would otherwise fire a burst.
  assert.equal(
    shouldFetchOlderMessages({ isUserScroll: true, geometry: longThread, hasMore: true, isFetching: true }),
    false,
  );
});

test('nothing older left means no request', () => {
  assert.equal(
    shouldFetchOlderMessages({ isUserScroll: true, geometry: longThread, hasMore: false, isFetching: false }),
    false,
  );
});

test('mid-thread scrolling does not page', () => {
  assert.equal(
    shouldFetchOlderMessages({
      isUserScroll: true,
      geometry: { scrollTop: 3000, scrollHeight: 7045, clientHeight: 148 },
      hasMore: true,
      isFetching: false,
    }),
    false,
  );
});
