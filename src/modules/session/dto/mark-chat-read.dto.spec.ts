import { validateSync } from 'class-validator';
import { plainToInstance } from 'class-transformer';
import { MARK_READ_MESSAGE_IDS_MAX, MarkChatReadDto } from './mark-chat-read.dto';

const errorCount = (chatId: unknown): number => validateSync(plainToInstance(MarkChatReadDto, { chatId })).length;

describe('MarkChatReadDto chatId validation', () => {
  // Engine-neutral: accept any active engine's JID scheme — whatsapp-web.js (@c.us/@g.us/@lid)
  // AND a swapped engine like Baileys (@s.whatsapp.net). The adapter validates/normalises further.
  it.each(['1234567890@c.us', '1234567890-123@g.us', '1234567890@lid', '1234567890@s.whatsapp.net'])(
    'accepts a valid JID across engines: %s',
    chatId => {
      expect(errorCount(chatId)).toBe(0);
    },
  );

  it.each(['', 'not-a-jid', 'no-at-host', '1234567890@', '@host.example', 'has space@c.us'])(
    'rejects a malformed chatId: %s',
    chatId => {
      expect(errorCount(chatId)).toBeGreaterThan(0);
    },
  );
});

const messageIdErrors = (messageIds: unknown): number =>
  validateSync(plainToInstance(MarkChatReadDto, { chatId: '1234567890@c.us', messageIds })).length;

describe('MarkChatReadDto messageIds validation', () => {
  it('accepts the field being absent — it is what every pre-existing caller sends', () => {
    expect(validateSync(plainToInstance(MarkChatReadDto, { chatId: '1234567890@c.us' })).length).toBe(0);
  });

  it('accepts a list of ids', () => {
    expect(messageIdErrors(['3EB0C767D26B8A3F1A2B', '3EB0C767D26B8A3F1A2C'])).toBe(0);
  });

  it('rejects an explicit null instead of letting it reach the engine', () => {
    // @IsOptional() skips every validator for null as well as undefined, so `"messageIds": null`
    // used to pass validation and then dereference in the adapter as a 500.
    expect(messageIdErrors(null)).toBeGreaterThan(0);
  });

  it('rejects an empty list rather than reading it as "the newest message"', () => {
    // The engine treats a missing list as "acknowledge the newest message". A caller that computed
    // its unread set and got none back must not land in that branch.
    expect(messageIdErrors([])).toBeGreaterThan(0);
  });

  it('accepts a full batch and rejects one over the cap', () => {
    const id = (n: number): string => `MSG${n}`;
    expect(messageIdErrors(Array.from({ length: MARK_READ_MESSAGE_IDS_MAX }, (_, i) => id(i)))).toBe(0);
    expect(messageIdErrors(Array.from({ length: MARK_READ_MESSAGE_IDS_MAX + 1 }, (_, i) => id(i)))).toBeGreaterThan(0);
  });

  it.each([[['  ']], [['']], [['has space']], [['ok', '  ']], [[123]], ['not-an-array']])(
    'rejects a malformed entry: %j',
    messageIds => {
      expect(messageIdErrors(messageIds)).toBeGreaterThan(0);
    },
  );
});
