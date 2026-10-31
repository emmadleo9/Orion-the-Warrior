import type { WASocket } from '@whiskeysockets/baileys';
import { BaileysContacts, type BaileysContactsHost } from './baileys-contacts';
import { createLogger } from '../../common/services/logger.service';
import type { Contact } from '../interfaces/whatsapp-engine.interface';

/**
 * `toNeutralContact` returned the literal `isBlocked: false` for every contact — not derived from
 * anything — while the SAME session's `/contacts/blocked` endpoint returned the real ids. Automation
 * that skips blocked contacts before sending therefore messaged people the account had explicitly
 * blocked, on the strength of a field the gateway had simply made up.
 */
const logger = createLogger('baileys-contact-blocked.spec');

describe('Baileys contact reads report real blocklist state', () => {
  const contact = (id: string): Contact => ({
    id,
    number: id.split('@')[0],
    isMyContact: true,
    isBlocked: false,
    pushName: 'x',
  });

  function make(opts: { blocklist?: string[]; blocklistError?: Error }): {
    contacts: BaileysContacts;
    warn: jest.Mock;
    fetchBlocklist: jest.Mock;
  } {
    const warn = jest.fn();
    const fetchBlocklist = opts.blocklistError
      ? jest.fn().mockRejectedValue(opts.blocklistError)
      : jest.fn().mockResolvedValue(opts.blocklist ?? []);
    const host = {
      ensureReady: jest.fn(),
      getSocket: () =>
        ({ fetchBlocklist, updateBlockStatus: jest.fn().mockResolvedValue(undefined) }) as unknown as WASocket,
      logger: { ...logger, warn },
      listContacts: () => [contact('628111@c.us'), contact('628222@c.us')],
      findContact: (id: string) => contact(id),
      toNeutralJid: (jid: string) => jid,
    } as unknown as BaileysContactsHost;
    return { contacts: new BaileysContacts(host), warn, fetchBlocklist };
  }

  it('marks a contact on the blocklist as blocked', async () => {
    const { contacts } = make({ blocklist: ['628222@c.us'] });

    const all = await contacts.getContacts();

    expect(all.find(c => c.id === '628222@c.us')?.isBlocked).toBe(true);
    expect(all.find(c => c.id === '628111@c.us')?.isBlocked).toBe(false);
  });

  it('marks a single contact read the same way', async () => {
    const { contacts } = make({ blocklist: ['628222@c.us'] });

    await expect(contacts.getContactById('628222@c.us')).resolves.toMatchObject({ isBlocked: true });
    await expect(contacts.getContactById('628111@c.us')).resolves.toMatchObject({ isBlocked: false });
  });

  // A blocklist query that fails is a transport fact, not a claim that nobody is blocked. The read
  // must not fail outright either — contacts are still useful — so it degrades loudly.
  // Regression guard for a cost this fix introduced: getContactById is called once per unique poster
  // when a session seeds its status history (session-engine-leaf-events resolvePoster), purely to
  // read a NAME. Querying the blocklist on each of those turned one connect into N network
  // round-trips, each with its own deadline. Memoised so a burst shares one query.
  it('issues ONE blocklist query for a burst of reads', async () => {
    const { contacts, fetchBlocklist } = make({ blocklist: [] });

    await contacts.getContactById('628111@c.us');
    await contacts.getContactById('628222@c.us');
    await contacts.getContacts();

    expect(fetchBlocklist).toHaveBeenCalledTimes(1);
  });

  // The memo must not outlive a change made through this same API: block() and unblock() clear it,
  // and without that a contact just blocked still reads isBlocked=false for the memo window.
  it('re-queries after a block, so a just-changed state is not read stale', async () => {
    const { contacts, fetchBlocklist } = make({ blocklist: [] });
    await contacts.getContactById('628111@c.us');
    expect(fetchBlocklist).toHaveBeenCalledTimes(1);

    await contacts.blockContact('628111@c.us');
    await contacts.getContactById('628111@c.us');

    expect(fetchBlocklist).toHaveBeenCalledTimes(2);
  });

  it('re-queries after an unblock for the same reason', async () => {
    const { contacts, fetchBlocklist } = make({ blocklist: ['628111@c.us'] });
    await contacts.getContactById('628111@c.us');
    await contacts.unblockContact('628111@c.us');
    await contacts.getContactById('628111@c.us');

    expect(fetchBlocklist).toHaveBeenCalledTimes(2);
  });

  it('does not fail the contact read when the blocklist query does, and says so', async () => {
    const { contacts, warn } = make({
      blocklistError: new Error('WhatsApp did not answer the blocklist query in time'),
    });

    const all = await contacts.getContacts();

    expect(all).toHaveLength(2);
    expect(warn).toHaveBeenCalled();
  });
});

/**
 * The memo exists to keep a contact read cheap, and every case above proves it with a query that
 * settles instantly — the one case that never needed a memo. Contact reads used to come straight
 * out of the in-memory store; they now await a blocklist query bounded only by the 30s engine
 * deadline, so the memo is what stands between a slow link and a status seed that resolves each
 * poster through getContactById paying that deadline again per poster.
 *
 * Both defects below are invisible to an instantly-resolving mock, which is why they shipped.
 */
describe('the blocklist memo holds under the conditions it exists for', () => {
  const contact = (id: string): Contact => ({
    id,
    number: id.split('@')[0],
    isMyContact: true,
    isBlocked: false,
    pushName: 'x',
  });

  /** Build an adapter whose blocklist query behaves however the test needs. */
  function withQuery(fetchBlocklist: jest.Mock): BaileysContacts {
    const host = {
      ensureReady: jest.fn(),
      getSocket: () =>
        ({ fetchBlocklist, updateBlockStatus: jest.fn().mockResolvedValue(undefined) }) as unknown as WASocket,
      logger: { ...createLogger('memo.spec'), warn: jest.fn() },
      listContacts: () => [contact('628111@c.us')],
      findContact: (id: string) => contact(id),
      toNeutralJid: (jid: string) => jid,
    } as unknown as BaileysContactsHost;
    return new BaileysContacts(host);
  }

  afterEach(() => jest.restoreAllMocks());

  /**
   * The memo was stamped with the time read BEFORE the query, so an answer that took longer than
   * the 5s window was written already expired — the memo absorbed only the fast queries and
   * collapsed on exactly the slow ones it was added for.
   */
  it('memoises an answer that took longer than the memo window', async () => {
    let clock = 1_000_000;
    jest.spyOn(Date, 'now').mockImplementation(() => clock);
    // Each query costs 6s of virtual time — longer than BLOCKLIST_MEMO_MS (5s).
    const fetchBlocklist = jest.fn().mockImplementation(() => {
      clock += 6_000;
      return Promise.resolve([]);
    });
    const contacts = withQuery(fetchBlocklist);

    await contacts.getContactById('628111@c.us');
    await contacts.getContactById('628111@c.us');

    expect(fetchBlocklist).toHaveBeenCalledTimes(1);
  });

  // Control: the memo must still EXPIRE, or the test above would pass on a memo that never refreshes.
  it('still re-queries once the window has genuinely passed', async () => {
    let clock = 1_000_000;
    jest.spyOn(Date, 'now').mockImplementation(() => clock);
    const fetchBlocklist = jest.fn().mockResolvedValue([]);
    const contacts = withQuery(fetchBlocklist);

    await contacts.getContactById('628111@c.us');
    clock += 5_001;
    await contacts.getContactById('628111@c.us');

    expect(fetchBlocklist).toHaveBeenCalledTimes(2);
  });

  /**
   * Nothing held the in-flight query, so callers that arrived while one was open each started their
   * own — the burst the memo names as its reason was the burst it could not collapse.
   */
  /**
   * Sharing one in-flight query introduces a window the per-read query did not have: a block landing
   * while a query is open. That answer describes the state BEFORE the block, so memoising it would
   * re-establish, for the whole window, exactly the staleness the block's invalidation exists to
   * clear — and the caller who just blocked someone would read them as unblocked.
   */
  it('does not memoise an answer that a block overtook while it was in flight', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>(resolve => {
      release = resolve;
    });
    const fetchBlocklist = jest
      .fn()
      .mockImplementationOnce(() => gate.then(() => [])) // pre-block answer: nobody blocked
      .mockResolvedValue(['628111@c.us']); // post-block truth
    const contacts = withQuery(fetchBlocklist);

    const inFlight = contacts.getContactById('628111@c.us');
    await contacts.blockContact('628111@c.us');
    release();
    await inFlight;

    // The stale answer must not be serving reads: this one has to go back to the socket.
    await expect(contacts.getContactById('628111@c.us')).resolves.toMatchObject({ isBlocked: true });
    expect(fetchBlocklist).toHaveBeenCalledTimes(2);
  });

  /**
   * Deriving isBlocked turned a contact read from an in-memory lookup into one that AWAITS a network
   * query. Sharing the engine's 30s budget with `/contacts/blocked` meant an unanswered blocklist —
   * the case `withQueryDeadline` exists for, since Baileys' own query() swallows its timeout — held
   * `GET /contacts` for half a minute. The enrichment is not the payload: past a short deadline the
   * contacts are returned with isBlocked at its default, which is the documented degradation.
   */
  it('returns the contacts rather than waiting out the engine budget on a hung blocklist', async () => {
    jest.useFakeTimers();
    try {
      const fetchBlocklist = jest.fn().mockImplementation(() => new Promise<string[]>(() => undefined));
      const contacts = withQuery(fetchBlocklist);

      const reading = contacts.getContacts();
      await jest.advanceTimersByTimeAsync(6_000); // past the enrichment deadline, far short of 30s

      await expect(reading).resolves.toEqual([expect.objectContaining({ id: '628111@c.us', isBlocked: false })]);
    } finally {
      jest.useRealTimers();
    }
  });

  /**
   * The in-flight handle is a single field, so the query that clears it must be the one that owns
   * it. After an invalidation the field belongs to the query started AFTER the block — an earlier
   * query settling later cleared that newer handle, and the next reader opened a third query while
   * the second was still open. The leak is precisely in the window the in-flight sharing created.
   */
  it('an overtaken query does not clear the handle of the one that replaced it', async () => {
    const gates: Array<() => void> = [];
    const openGate = (): Promise<string[]> =>
      new Promise<string[]>(resolve => {
        gates.push(() => resolve([]));
      });
    const fetchBlocklist = jest.fn().mockImplementation(openGate);
    const contacts = withQuery(fetchBlocklist);

    const first = contacts.getContactById('628111@c.us'); // Q1 owns the handle
    await contacts.blockContact('628111@c.us'); // invalidates: handle cleared, generation bumped
    const second = contacts.getContactById('628111@c.us'); // Q2 takes the handle
    expect(fetchBlocklist).toHaveBeenCalledTimes(2);

    gates[0](); // Q1 settles late — it must not touch Q2's handle
    await first;

    // Q2 is still open, so this reader has to JOIN it rather than open a third query.
    const third = contacts.getContactById('628111@c.us');
    expect(fetchBlocklist).toHaveBeenCalledTimes(2);

    gates[1]();
    await Promise.all([second, third]);
  });

  it('collapses a burst of concurrent reads onto one query', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>(resolve => {
      release = resolve;
    });
    const fetchBlocklist = jest.fn().mockImplementation(() => gate.then(() => []));
    const contacts = withQuery(fetchBlocklist);

    const reads = Promise.all([
      contacts.getContactById('628111@c.us'),
      contacts.getContactById('628111@c.us'),
      contacts.getContactById('628111@c.us'),
    ]);
    release();
    await reads;

    expect(fetchBlocklist).toHaveBeenCalledTimes(1);
  });
});
