import { ValidatorConstraint, ValidatorConstraintInterface } from 'class-validator';

/**
 * Whether a string can survive the round trip into `allowedSessions` and still mean what was sent.
 *
 * The column is `simple-array`, which TypeORM stores as a comma join and reads back with a comma
 * split. Two shapes therefore do not survive it, and both fail OPEN rather than closed:
 *
 * - An empty or whitespace-only entry. `[""]` joins to `''`, reads back as `[]`, and every
 *   enforcement site treats a zero-length list as "every session". A request that looked like a
 *   scoping landed as a widening, which is the opposite of what the caller asked for.
 * - An entry containing a comma. `["a,b"]` reads back as two entries, so the stored allowlist is
 *   not the one that was sent.
 *
 * Deliberately NOT a UUID rule, even though session ids are always server-generated UUIDs. A
 * non-UUID entry fails CLOSED (it matches no session), so it is a usability wart rather than a
 * security hole, while a UUID rule would reject an operator re-saving a key whose allowlist holds a
 * legacy or imported id.
 */
export function isSessionId(value: unknown): boolean {
  return typeof value === 'string' && value.trim() === value && value.length > 0 && !value.includes(',');
}

@ValidatorConstraint({ name: 'isSessionId', async: false })
export class IsSessionIdConstraint implements ValidatorConstraintInterface {
  validate(value: unknown): boolean {
    return isSessionId(value);
  }
  defaultMessage(): string {
    return 'each allowedSessions entry must be a non-empty session id with no surrounding whitespace and no comma';
  }
}
