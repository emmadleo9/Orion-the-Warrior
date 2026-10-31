/**
 * How many sessions WhatsApp is currently restricting, for the Prometheus gauge.
 *
 * A gauge and not a counter: what an operator alerts on is "an account is restricted right now", and
 * a restriction that is applied, lifted and re-applied is the same one fact recurring, not a total to
 * accumulate. The value is mirrored here rather than read from the store at render time so the
 * metrics module does not have to depend on the session module for one number —
 * `SessionRestrictionStore` is the single writer and republishes its own size after every mutation.
 *
 * The mirror is the FALLBACK, not what a scrape normally reads: once the store registers a live
 * recount, `getRestrictedSessionCount` calls that instead. A restriction that lapses by its own
 * `expiresAt` is not a mutation, so nothing republishes and the mirror would go stale exactly when
 * an alert on `> 0` is still firing.
 */
let restrictedSessions = 0;

/**
 * A live recount, registered by the store. The mirrored value above is refreshed on every mutation,
 * but a restriction that lapses by its own `expiresAt` is not a mutation — nothing fires, and the
 * gauge kept reporting the pre-expiry count while every read path already reported the session as
 * unrestricted. Registering a function rather than importing the store keeps the dependency pointing
 * one way: the session module knows about metrics, not the reverse.
 */
let recount: (() => number) | null = null;

/** Publish the current number of restricted sessions (called by SessionRestrictionStore). */
export function setRestrictedSessionCount(count: number): void {
  restrictedSessions = count;
}

/** Register the store's live recount. Called once, when the store is constructed. */
export function registerRestrictedSessionRecount(fn: () => number): void {
  recount = fn;
}

/** Sessions under a WhatsApp-imposed restriction at this moment. */
export function getRestrictedSessionCount(): number {
  return recount ? recount() : restrictedSessions;
}
