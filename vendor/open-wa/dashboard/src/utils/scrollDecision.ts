export interface ScrollGeometry {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

export type ScrollDirection = 'incoming' | 'outgoing';
export type ScrollAction = 'bottom' | 'preserve';

const DEFAULT_NEAR_BOTTOM_THRESHOLD = 100;

/**
 * Decide whether to scroll to bottom after a new message is appended.
 *
 * - Outgoing (user sent it) always scrolls — the user wants to see their own message.
 * - Incoming scrolls only when the user is already near the bottom (i.e. they're
 *   following the conversation). When the user has scrolled up to read older messages,
 *   we preserve their position so a new arrival doesn't yank them away.
 *
 * `geometry` should be captured BEFORE the new message has been committed to the DOM,
 * so `scrollHeight` reflects the pre-append state and the "near bottom" question
 * answers the user's current intent.
 */
export function decideScroll(
  direction: ScrollDirection,
  geometry: ScrollGeometry,
  nearBottomThreshold: number = DEFAULT_NEAR_BOTTOM_THRESHOLD,
): ScrollAction {
  if (direction === 'outgoing') return 'bottom';
  const gap = geometry.scrollHeight - geometry.scrollTop - geometry.clientHeight;
  return gap < nearBottomThreshold ? 'bottom' : 'preserve';
}

/** How close to the top counts as "reading back through the thread". */
const NEAR_TOP_THRESHOLD = 100;

/**
 * Decide whether reaching the top of the thread should pull the next older page.
 *
 * `isUserScroll` is load-bearing, not defensive. The thread's listener also runs a sync call on
 * every render to refresh the scroll-to-bottom button, and a freshly opened room reports
 * `scrollTop` 0 there — which reads as "at the top". Paging from that call cascaded: each page
 * re-rendered, re-ran the sync call at scrollTop 0 and asked for the next one, so opening a chat
 * pulled its whole history in one burst instead of a page at a time.
 *
 * The scrollable check covers the same shape from the other side: a thread shorter than its
 * viewport sits at scrollTop 0 permanently and would page forever on any stray event.
 */
export function shouldFetchOlderMessages(args: {
  isUserScroll: boolean;
  geometry: ScrollGeometry;
  hasMore: boolean;
  isFetching: boolean;
}): boolean {
  const { isUserScroll, geometry, hasMore, isFetching } = args;
  if (!isUserScroll || !hasMore || isFetching) return false;
  if (geometry.scrollHeight <= geometry.clientHeight) return false;
  return geometry.scrollTop < NEAR_TOP_THRESHOLD;
}
