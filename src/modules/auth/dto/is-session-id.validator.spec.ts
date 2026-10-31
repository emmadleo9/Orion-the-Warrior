import { validate } from 'class-validator';
import { plainToInstance } from 'class-transformer';
import { isSessionId } from './is-session-id.validator';
import { CreateApiKeyDto, UpdateApiKeyDto } from './api-key.dto';

/**
 * `allowedSessions` is stored in a `simple-array` column: TypeORM joins on write and splits on
 * read. Two entry shapes therefore do not survive the round trip, and both fail OPEN.
 *
 * `['']` joins to `''`, reads back as `[]`, and every enforcement site treats a zero-length list as
 * "every session" — so a request that looked like a scoping landed as a widening. An entry holding
 * a comma comes back as two entries, so the stored allowlist is not the one that was sent.
 */
describe('isSessionId', () => {
  it.each(['0a941dac-a965-45e7-b318-74ae8be134f0', 'legacy-id', 'a'])('accepts %p', value => {
    expect(isSessionId(value)).toBe(true);
  });

  it.each([
    ['', 'empty: joins to the same string as an unscoped key'],
    ['   ', 'whitespace only: trims to empty'],
    [' id', 'leading space: never equals a stored id'],
    ['id ', 'trailing space: never equals a stored id'],
    ['a,b', 'comma: splits into two entries on read'],
  ])('rejects %p (%s)', value => {
    expect(isSessionId(value)).toBe(false);
  });

  it.each([undefined, null, 42, {}, []])('rejects the non-string %p', value => {
    expect(isSessionId(value)).toBe(false);
  });
});

describe('allowedSessions validation on the DTOs', () => {
  const errorsFor = async (Dto: typeof CreateApiKeyDto | typeof UpdateApiKeyDto, allowedSessions: unknown) => {
    const dto = plainToInstance(Dto, { name: 'k', allowedSessions });
    const errors = await validate(dto, { whitelist: true });
    return errors.filter(e => e.property === 'allowedSessions');
  };

  it.each([CreateApiKeyDto, UpdateApiKeyDto])('%p refuses the fail-open [""]', async Dto => {
    expect(await errorsFor(Dto, [''])).not.toHaveLength(0);
  });

  it.each([CreateApiKeyDto, UpdateApiKeyDto])('%p refuses a comma-bearing entry', async Dto => {
    expect(await errorsFor(Dto, ['a,b'])).not.toHaveLength(0);
  });

  it.each([CreateApiKeyDto, UpdateApiKeyDto])('%p refuses duplicates', async Dto => {
    expect(await errorsFor(Dto, ['same', 'same'])).not.toHaveLength(0);
  });

  // The unscoped forms stay valid: they are the documented way to grant every session.
  it.each([CreateApiKeyDto, UpdateApiKeyDto])('%p still accepts an empty list and a real id', async Dto => {
    expect(await errorsFor(Dto, [])).toHaveLength(0);
    expect(await errorsFor(Dto, ['0a941dac-a965-45e7-b318-74ae8be134f0'])).toHaveLength(0);
    expect(await errorsFor(Dto, undefined)).toHaveLength(0);
  });
});
