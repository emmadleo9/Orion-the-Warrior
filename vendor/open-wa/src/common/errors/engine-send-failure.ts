/** Record that an error escaped an engine send, independently of its HTTP status. */
const attemptedSendFailures = new WeakSet<object>();

export function markEngineSendFailure<T>(error: T): T {
  if (error !== null && typeof error === 'object') attemptedSendFailures.add(error);
  return error;
}

export function isEngineSendFailure(error: unknown): boolean {
  return error !== null && typeof error === 'object' && attemptedSendFailures.has(error);
}
