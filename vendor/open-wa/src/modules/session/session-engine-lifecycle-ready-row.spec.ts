import { readyRowUpdate } from './session-engine-lifecycle.service';
import { SessionStatus } from './entities/session.entity';

/**
 * whatsapp-web.js can report an empty phone at ready (client.info momentarily unreadable). The
 * account-binding guard skips an empty incoming phone rather than rebind-rejecting it, so if the
 * ready row write also clobbered the stored phone with '', the binding would be silently dropped
 * until the next non-empty ready. readyRowUpdate keeps the bound number in that case.
 */
describe('readyRowUpdate', () => {
  const at = new Date('2026-01-01T00:00:00.000Z');

  it('writes the phone when the ready reports one', () => {
    expect(readyRowUpdate('628111', 'Alice', at)).toEqual({
      status: SessionStatus.READY,
      phone: '628111',
      pushName: 'Alice',
      connectedAt: at,
      lastActiveAt: at,
    });
  });

  it('omits phone on an empty-phone ready, keeping the bound number', () => {
    const update = readyRowUpdate('', 'Alice', at);
    expect(update).not.toHaveProperty('phone');
    expect(update).toMatchObject({
      status: SessionStatus.READY,
      pushName: 'Alice',
      connectedAt: at,
      lastActiveAt: at,
    });
  });
});
