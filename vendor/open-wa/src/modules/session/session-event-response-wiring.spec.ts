import { SessionEngineEventWiring, SessionEngineWiringHost } from './session-engine-event-wiring';
import { EventResponseEvent, IWhatsAppEngine } from '../../engine/interfaces/whatsapp-engine.interface';
import { createLogger } from '../../common/services/logger.service';

describe('event.response wiring', () => {
  const rsvp: EventResponseEvent = {
    eventMessageId: 'EVT1',
    chatId: '120363000000000001@g.us',
    responderId: '51987654321@c.us',
    contact: { name: 'Ana Pérez', pushName: 'Ana' },
    fromMe: false,
    response: 'going',
    responseMessageId: 'RSVP1',
    timestamp: 1786000000,
  };

  const setup = (live: boolean) => {
    const dispatch = jest.fn();
    const emitEventResponse = jest.fn();
    const host = {
      isLiveEngine: () => live,
      messages: {},
      webhookService: { dispatch },
      eventsGateway: { emitEventResponse },
    } as unknown as SessionEngineWiringHost;
    const cb = new SessionEngineEventWiring({ logger: createLogger('test') }).buildCallbacks(
      'sess-1',
      {} as IWhatsAppEngine,
      'sess-1-name',
      host,
    );
    return { cb, dispatch, emitEventResponse };
  };

  it('publishes the RSVP with its session to the webhook and the WebSocket', () => {
    const { cb, dispatch, emitEventResponse } = setup(true);

    cb.onEventResponse?.(rsvp);

    const payload = { sessionId: 'sess-1', ...rsvp };
    expect(dispatch).toHaveBeenCalledWith('sess-1', 'event.response', payload);
    expect(emitEventResponse).toHaveBeenCalledWith('sess-1', payload);
  });

  it('publishes nothing from an engine that is no longer live', () => {
    const { cb, dispatch, emitEventResponse } = setup(false);

    cb.onEventResponse?.(rsvp);

    expect(dispatch).not.toHaveBeenCalled();
    expect(emitEventResponse).not.toHaveBeenCalled();
  });
});
