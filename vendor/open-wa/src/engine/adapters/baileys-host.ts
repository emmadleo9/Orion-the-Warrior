import { type BaileysEventsHost } from './baileys-events';
import { type BaileysGroupsHost } from './baileys-groups';
import { type BaileysMessagingHost } from './baileys-messaging';
import { type BaileysContactsHost } from './baileys-contacts';
import { type BaileysStatusHost } from './baileys-status';
import { type BaileysChannelsHost } from './baileys-channels';
import { type BaileysCatalogHost } from './baileys-catalog';
import { type BaileysHistoryHost } from './baileys-history';
import { type BaileysLifecycleHost } from './baileys-lifecycle';

/**
 * The single host surface handed to every Baileys delegate, mirroring the wwebjs-host pattern:
 * the adapter builds ONE object literal of these closures and gives it to each delegate, so a new
 * cross-cutting member (a jid helper, a callback getter) is added once instead of to up to eight
 * per-delegate literals. Each delegate still declares its own narrow Host interface - the literal
 * satisfies them all structurally, and the narrow interfaces keep documenting what a delegate may
 * touch (least privilege: a delegate cannot accidentally grow dependencies on the full surface).
 */
export type BaileysEngineHost = BaileysEventsHost &
  BaileysGroupsHost &
  BaileysMessagingHost &
  BaileysContactsHost &
  BaileysStatusHost &
  BaileysChannelsHost &
  BaileysCatalogHost &
  BaileysHistoryHost &
  BaileysLifecycleHost;
