import { BadRequestException } from '@nestjs/common';
import { applySendingGate } from './sending-gate';
import { HookManager } from './hook-manager.service';
import { LoggerService } from '../../common/services/logger.service';

/**
 * The gate returned `(hookData as { input: T }).input` with no check that the hook chain's reply
 * still carried an envelope. A `message:sending` handler returning any other truthy object made the
 * gate hand `undefined` to the caller, which then dereferenced it — one plugin authoring mistake
 * turned EVERY outbound send on that session into an unhandled TypeError and a 500 whose text named
 * no plugin. A `data: null` made the gate itself throw. Nothing covered this file at all.
 */
describe('applySendingGate', () => {
  const dto = { chatId: 'c@c.us', text: 'hi' };
  const gate = (result: unknown): Promise<typeof dto> =>
    applySendingGate(
      { execute: jest.fn().mockResolvedValue(result) } as unknown as HookManager,
      's1',
      'text',
      dto,
      'MessageService',
    );

  it('returns the plugin-modified input when the envelope is intact', async () => {
    const rewritten = { chatId: 'c@c.us', text: 'redacted' };
    await expect(gate({ continue: true, data: { input: rewritten } })).resolves.toEqual(rewritten);
  });

  // A stub manager, deliberately: HookManager itself always answers with an envelope (runHandlers
  // returns the data it was given when no handler is registered), so this branch is defensive rather
  // than a path production reaches. Pinned anyway — it is what stops a manager that answers with
  // nothing from being read as a veto.
  it('returns the original input when the chain replies with no data at all', async () => {
    await expect(gate({ continue: true })).resolves.toEqual(dto);
  });

  it('still refuses a send the plugin vetoed', async () => {
    await expect(gate({ continue: false, data: { input: dto } })).rejects.toThrow(BadRequestException);
  });

  // Fail CLOSED, and say why. This is a moderation chokepoint: a handler whose reply cannot be read
  // may have been trying to redact something, so proceeding with the original would be a bypass.
  it.each([
    ['a truthy object with no input', { continue: true, data: { notInput: 1 } }],
    ['a null data', { continue: true, data: null }],
    ['a primitive data', { continue: true, data: 'ok' }],
    ['an input that is not an object', { continue: true, data: { input: 'text' } }],
  ])('refuses the send when the hook returns %s', async (_label, result) => {
    await expect(gate(result)).rejects.toThrow(BadRequestException);
    await expect(gate(result)).rejects.toThrow(/message:sending/);
  });

  /**
   * The 400 goes to the API caller, who is not the person who can fix it: a plugin returning a bad
   * envelope stops EVERY send on that session, and the operator's only evidence was a client-side
   * error they never see. The refusal has to leave a trace on the server, carrying the session and
   * the call site so the failing session is identifiable.
   */
  describe('leaves the operator a trace', () => {
    let warn: jest.SpyInstance;
    beforeEach(() => {
      warn = jest.spyOn(LoggerService.prototype, 'warn').mockImplementation(() => undefined);
    });
    afterEach(() => warn.mockRestore());

    it('warns, naming the session and the call site, when the envelope is unusable', async () => {
      await expect(gate({ continue: true, data: { notInput: 1 } })).rejects.toThrow(BadRequestException);

      expect(warn).toHaveBeenCalledTimes(1);
      const [message, context] = warn.mock.calls[0] as [string, Record<string, unknown>];
      expect(message).toMatch(/message:sending/);
      expect(context).toMatchObject({ sessionId: 's1', source: 'MessageService', type: 'text' });
    });

    // Negative twin: the ordinary paths must stay quiet, or the signal is worthless.
    it.each([
      ['an intact envelope', { continue: true, data: { input: { chatId: 'c@c.us', text: 'hi' } } }],
      ['no data at all', { continue: true }],
    ])('stays silent on %s', async (_label, result) => {
      await gate(result);
      expect(warn).not.toHaveBeenCalled();
    });
  });
});
