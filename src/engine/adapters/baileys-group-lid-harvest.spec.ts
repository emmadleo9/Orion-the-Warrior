import type { GroupMetadata } from '@whiskeysockets/baileys';
import type { WASocket } from '@whiskeysockets/baileys';
import { BaileysGroups, BaileysGroupsHost, collectGroupLidTwins } from './baileys-groups';

/**
 * The group roster carries each member's phone twin inline (`participant.phoneNumber`, `metadata.ownerPn`),
 * but `resolvePhone` reads only the lid map that 1:1 traffic feeds. A member present solely in a roster
 * resolved to `null` on `GET /contacts/{lid}/phone` (#1510). getGroupInfo now harvests the roster twins
 * into that map, and only the @lid-addressed ones (a phone-addressed participant would key a bogus pair).
 */
const meta = (over: Partial<GroupMetadata> = {}): GroupMetadata =>
  ({
    id: '120363000000000000@g.us',
    subject: 'Ops',
    owner: '111222333@lid',
    ownerPn: '628111@s.whatsapp.net',
    creation: 1,
    participants: [
      { id: '111222333@lid', phoneNumber: '628111@s.whatsapp.net', admin: 'superadmin' },
      { id: '444555666@lid', phoneNumber: '628222@s.whatsapp.net', admin: null },
      // @lid with no server-sent twin (non-contact privacy default): nothing to harvest.
      { id: '777888999@lid', phoneNumber: undefined, admin: null },
      // already phone-addressed: no lid to key, must NOT become a phone->phone pair.
      { id: '628333@s.whatsapp.net', phoneNumber: '628333@s.whatsapp.net', admin: null },
    ],
    ...over,
  }) as unknown as GroupMetadata;

describe('collectGroupLidTwins', () => {
  it('harvests only @lid participants that carry a phone twin, plus the @lid owner', () => {
    expect(collectGroupLidTwins(meta())).toEqual([
      { lid: '111222333@lid', pn: '628111@s.whatsapp.net' },
      { lid: '444555666@lid', pn: '628222@s.whatsapp.net' },
      { lid: '111222333@lid', pn: '628111@s.whatsapp.net' },
    ]);
  });

  it('skips the owner when it is phone-addressed or has no twin', () => {
    expect(collectGroupLidTwins(meta({ owner: '628111@s.whatsapp.net', ownerPn: undefined }))).toEqual([
      { lid: '111222333@lid', pn: '628111@s.whatsapp.net' },
      { lid: '444555666@lid', pn: '628222@s.whatsapp.net' },
    ]);
    expect(collectGroupLidTwins(meta({ owner: '111222333@lid', ownerPn: undefined }))).toEqual([
      { lid: '111222333@lid', pn: '628111@s.whatsapp.net' },
      { lid: '444555666@lid', pn: '628222@s.whatsapp.net' },
    ]);
  });

  it('returns nothing for an all-phone roster (no lids to key)', () => {
    const phoneOnly = meta({
      owner: '628111@s.whatsapp.net',
      ownerPn: undefined,
      participants: [{ id: '628111@s.whatsapp.net', phoneNumber: '628111@s.whatsapp.net', admin: null }] as never,
    });
    expect(collectGroupLidTwins(phoneOnly)).toEqual([]);
  });
});

describe('getGroupInfo harvests the roster twins into the lid map', () => {
  const build = (metadata: GroupMetadata) => {
    const addLidMappings = jest.fn();
    const host = {
      ensureReady: () => undefined,
      getSocket: () => ({ groupMetadata: jest.fn().mockResolvedValue(metadata) }) as unknown as WASocket,
      logger: { warn: jest.fn(), debug: jest.fn(), info: jest.fn(), error: jest.fn() },
      toNeutralJid: (j: string) => j,
      toEngineJid: (j: string) => j,
      normalizedSelfJid: () => '628111@s.whatsapp.net',
      addLidMappings,
    } as unknown as BaileysGroupsHost;
    return { groups: new BaileysGroups(host, 500), addLidMappings };
  };

  it('feeds the collected @lid twins to addLidMappings on a successful read', async () => {
    const { groups, addLidMappings } = build(meta());
    await groups.getGroupInfo('120363000000000000@g.us');
    expect(addLidMappings).toHaveBeenCalledWith(collectGroupLidTwins(meta()));
  });
});
