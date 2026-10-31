import { BadRequestException, HttpException, NotFoundException } from '@nestjs/common';
import { WwebjsLifecycle } from './wwebjs-lifecycle';
import { MessageNotFoundError } from '../../common/errors/message-not-found.error';
import { GroupNotFoundError } from '../../common/errors/group-not-found.error';
import { EngineTransportError } from '../../common/errors/engine-transport.error';

/**
 * The dead-page classifier must never read an error this application constructed.
 *
 * Its domain errors interpolate caller-supplied identifiers verbatim, so matching a message pattern
 * against one hands the CALLER the classifier. A request naming a messageId of "Target closed" made
 * its own 404 look like a transport death: the session was torn down and reconnected, spurious
 * session.disconnected events went out to every consumer, inbound delivery paused for the
 * reconnect, and the honest 404 came back as a 503 that the Go client replays. The reactions read
 * carries no role requirement, so the lowest-privilege key could do it on demand, repeatedly.
 *
 * The classifier is the one funnel: `withPage` and every open-coded guard in the chats, contacts,
 * groups, labels and messaging delegates route through it, so one exclusion covers them all.
 */
describe('isPageTransportError', () => {
  // The method reads only static patterns, so a bare prototype call is enough and avoids standing
  // up a Client, a logger and an auth path that have nothing to do with the classification.
  const classify = (error: unknown): boolean => WwebjsLifecycle.prototype.isPageTransportError.call({}, error);

  describe('an error the application constructed is never a dead page', () => {
    it.each([
      ['Target closed', undefined],
      ['protocol error', '628123@c.us'],
      ['Session closed', '628123@c.us'],
      ['detached frame', '628123@c.us'],
      ['connection closed', '628123@c.us'],
      ['TargetCloseError', '628123@c.us'],
    ])('a messageId of %p does not classify as one', (messageId, chatId) => {
      const error = new MessageNotFoundError(messageId, chatId);

      // The poisoned text really is in the message; the guard is what stops it mattering.
      expect(error.message).toContain(messageId);
      expect(classify(error)).toBe(false);
    });

    it('covers the sibling domain errors that carry caller text the same way', () => {
      expect(classify(new GroupNotFoundError('Target closed'))).toBe(false);
      expect(classify(new NotFoundException('Target closed'))).toBe(false);
      expect(classify(new BadRequestException('protocol error'))).toBe(false);
    });

    /**
     * An EngineTransportError extends ServiceUnavailableException, so it is excluded too. That is
     * correct rather than a gap: every site that builds one has already reported the death, and the
     * teardown latches on status, so a second report would change nothing.
     */
    it('does not re-classify an EngineTransportError from an inner catch', () => {
      const error = new EngineTransportError('Transport died during getChatById');

      expect(error).toBeInstanceOf(HttpException);
      expect(classify(error)).toBe(false);
    });
  });

  describe('a real transport death still classifies', () => {
    it.each([
      'Protocol error (Runtime.callFunctionOn): Target closed',
      'Protocol error (Page.navigate): Session closed. Most likely the page has been closed.',
      "Attempted to use detached Frame 'ABC'.",
      'Execution context is not available in detached frame or worker "x" (are you using frame.evaluate after navigation?)',
      'Connection closed',
    ])('%p', message => {
      expect(classify(new Error(message))).toBe(true);
    });

    it('still classifies a non-Error thrown value carrying the signature', () => {
      expect(classify('Target closed')).toBe(true);
    });

    // The one message-shaped exclusion that predates this: a per-command budget overrun is the
    // renderer being slow, not gone, and the next command may well succeed.
    it('still refuses a puppeteer protocol timeout', () => {
      expect(
        classify(
          new Error(
            "Runtime.callFunctionOn timed out. Increase the 'protocolTimeout' setting in launch/connect calls for a higher timeout if needed.",
          ),
        ),
      ).toBe(false);
    });
  });
});
