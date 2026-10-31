import type { GroupMetadata } from '@whiskeysockets/baileys';
import { mapBaileysGroup, mapBaileysGroupInfo } from './baileys-group-mapper';

/**
 * The mappers read only `metadata.owner` and `participant.id` and discarded the phone-dialect twins
 * the SAME payload carries (`ownerPn`, `participant.phoneNumber`). For a LID-addressed group that
 * left `owner` and `participants[].id` as `<lid>@lid`, made `participants[].number` the LID digits
 * presented as a phone number, and made `isAdmin` false for the account that administers the group.
 *
 * The old behaviour was only correct once the lid→pn mapping had been LEARNED — the normalizer
 * resolves it then. These pin the cold arm, where nothing has been learned yet and the twin the
 * server already sent is the only phone-dialect source available.
 */
const identity = (jid: string): string => jid;

const lidGroup = (withTwins: boolean): GroupMetadata =>
  ({
    id: '12345-67890@g.us',
    subject: 'Ops',
    owner: '111222333@lid',
    ownerPn: withTwins ? '628111@s.whatsapp.net' : undefined,
    creation: 1,
    participants: [
      {
        id: '111222333@lid',
        phoneNumber: withTwins ? '628111@s.whatsapp.net' : undefined,
        admin: 'superadmin',
      },
      { id: '444555666@lid', phoneNumber: withTwins ? '628222@s.whatsapp.net' : undefined, admin: null },
    ],
  }) as unknown as GroupMetadata;

describe('LID group metadata uses the phone-dialect twins the payload already carries', () => {
  it('maps the owner from ownerPn', () => {
    expect(mapBaileysGroupInfo(lidGroup(true), identity).owner).toBe('628111@s.whatsapp.net');
  });

  it('maps participant ids and numbers from phoneNumber', () => {
    const info = mapBaileysGroupInfo(lidGroup(true), identity);

    expect(info.participants.map(p => p.id)).toEqual(['628111@s.whatsapp.net', '628222@s.whatsapp.net']);
    // The whole point: `number` must be an MSISDN, not the LID digits dressed up as one.
    expect(info.participants.map(p => p.number)).toEqual(['628111', '628222']);
  });

  it('recognises the account as admin through its phone-dialect twin', () => {
    expect(mapBaileysGroup(lidGroup(true), '628111@c.us', identity).isAdmin).toBe(true);
  });

  // Negative twin: WhatsApp withholds phone_number for non-contacts as a privacy default. With no
  // twin there is nothing to prefer, and the previous behaviour must stand rather than the mapper
  // inventing an MSISDN.
  it('falls back to the lid when the server sent no twin', () => {
    const info = mapBaileysGroupInfo(lidGroup(false), identity);

    expect(info.owner).toBe('111222333@lid');
    expect(info.participants.map(p => p.id)).toEqual(['111222333@lid', '444555666@lid']);
  });
});
