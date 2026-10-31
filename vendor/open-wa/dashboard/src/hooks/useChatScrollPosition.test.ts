import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  correctionForMediaGrowth,
  decideRestoreTarget,
  grewAboveReadingPosition,
  isNearBottom,
} from './useChatScrollPosition.ts';

test('isNearBottom: exactly at the bottom counts as near', () => {
  assert.equal(isNearBottom(1000, 2000, 1000), true); // 2000-1000-1000 = 0
});

test('isNearBottom: within the 24px tolerance counts as near', () => {
  assert.equal(isNearBottom(980, 2000, 1000), true); // 20px above bottom
});

test('isNearBottom: beyond the tolerance does not count', () => {
  assert.equal(isNearBottom(500, 2000, 1000), false); // 500px above bottom
});

test('isNearBottom: a scrolled-to-top container is not near the bottom', () => {
  assert.equal(isNearBottom(0, 20000, 800), false);
});

test('first render with no saved position: restore to bottom when loaded', () => {
  assert.deepEqual(decideRestoreTarget('A', true, undefined), { restore: 'bottom' });
});

test('first render still loading: no restore', () => {
  assert.deepEqual(decideRestoreTarget('A', false, undefined), { restore: null });
});

test('cold open: loading transition then loaded → restore to bottom', () => {
  assert.deepEqual(decideRestoreTarget('A', false, undefined), { restore: null });
  assert.deepEqual(decideRestoreTarget('A', true, undefined), { restore: 'bottom' });
});

test('returning to a chat with a saved position restores it (never bottom-jumps)', () => {
  // The scroll listener saves the live scrollTop continuously, so a round trip A → B → A finds A's
  // real last position in the map and restores it exactly.
  assert.deepEqual(decideRestoreTarget('A', true, 250), { restore: 'saved' });
});

test('a saved position of 0 is still a saved position (top of thread is a real place)', () => {
  assert.deepEqual(decideRestoreTarget('A', true, 0), { restore: 'saved' });
});

test('deselect chat (next is null): no restore', () => {
  assert.deepEqual(decideRestoreTarget(null, false, undefined), { restore: null });
});

// The container's top edge is the reading position: everything above it is scrolled out of view.
const CONTAINER_TOP = 100;

test('media entirely above the reading position displaced the view, so it is corrected', () => {
  // Bottom edge at 40, well clear of the container's top at 100.
  assert.equal(grewAboveReadingPosition(40, CONTAINER_TOP), true);
});

test('media whose bottom edge sits exactly on the top edge still counts as above', () => {
  assert.equal(grewAboveReadingPosition(CONTAINER_TOP, CONTAINER_TOP), true);
});

test('media below the reading position moved nothing on screen and is left alone', () => {
  // This is the case a bare scrollHeight delta got wrong: correcting here scrolls the reader
  // toward the newest messages by the decoded height, which is the opposite of holding position.
  assert.equal(grewAboveReadingPosition(450, CONTAINER_TOP), false);
});

test('media straddling the top edge is left uncorrected rather than over-corrected', () => {
  // Top above the edge, bottom below it: only the part above displaces, so a full correction
  // would overshoot. Answering false drifts with the reader rather than against them.
  assert.equal(grewAboveReadingPosition(160, CONTAINER_TOP), false);
});

// --- correctionForMediaGrowth -------------------------------------------------------------------
//
// The reading position is the container's top edge (CONTAINER_TOP, declared above). A media element
// that decodes above it pushes everything below down, so scrollTop has to grow by the same amount to
// keep the same content on screen.

// correctionForMediaGrowth returns the DELTA to add to a live scrollTop (or null), not an absolute
// target, so a second same-frame decode stacks on the first rather than overwriting it.
test('an element that decoded above the reader yields exactly its growth as the delta', () => {
  // Seeded 0px at mount, now 300px, and its post-decode bottom sits at 90: before it grew, its
  // bottom was at -210, well above the reading position.
  assert.equal(correctionForMediaGrowth(0, 300, 90, CONTAINER_TOP), 300);
});

/**
 * The case a baseline taken in the load handler could never see. By then the decoded height is
 * already in layout, so seeded === current, the growth reads as zero, and nothing is corrected
 * while the reader has in fact been displaced.
 */
test('a baseline equal to the current height yields no delta, which is why it is seeded at mount', () => {
  assert.equal(correctionForMediaGrowth(300, 300, 90, CONTAINER_TOP), null);
});

test('an element that decoded below the reader yields no delta', () => {
  // Grew 300, and even before growing its bottom was at 500: far below the top edge, so nothing
  // the reader can see moved. Correcting here would drag them toward the newest messages.
  assert.equal(correctionForMediaGrowth(0, 300, 800, CONTAINER_TOP), null);
});

/**
 * The subtraction is what makes the question answerable. Post-decode this element measures BELOW
 * the top edge (bottom 150 > 100), but it only got there by growing: before the decode its bottom
 * was at 50, above the reader, so it did displace them.
 */
test('the above/below question is asked against the pre-decode layout', () => {
  assert.equal(correctionForMediaGrowth(0, 100, 150, CONTAINER_TOP), 100);
});

test('a shrink or an unchanged box yields no delta', () => {
  assert.equal(correctionForMediaGrowth(300, 300, 50, CONTAINER_TOP), null);
  assert.equal(correctionForMediaGrowth(300, 120, 50, CONTAINER_TOP), null);
});

/**
 * Two above-the-fold elements decoding in one frame. Each returns its own growth as a delta, and
 * the caller adds each to the live scrollTop, so the reader is held through the SUM. Modelled here
 * as the caller does it: start at 1000, apply the first delta, then the second against the result.
 */
test('two same-frame deltas accumulate rather than overwrite', () => {
  const d1 = correctionForMediaGrowth(0, 300, 90, CONTAINER_TOP);
  const d2 = correctionForMediaGrowth(0, 300, 80, CONTAINER_TOP);
  assert.equal(d1, 300);
  assert.equal(d2, 300);
  let scrollTop = 1000;
  scrollTop += d1 as number;
  scrollTop += d2 as number;
  assert.equal(scrollTop, 1600); // 600 total, not 300
});
