import { SessionEngineEventWiring, SessionEngineWiringHost } from './session-engine-event-wiring';
import type { IncomingMessage, IWhatsAppEngine } from '../../engine/interfaces/whatsapp-engine.interface';
import { createLogger } from '../../common/services/logger.service';

describe('onMessage wiring', () => {
  const message = { id: 'M1', chatId: '628111@c.us', body: 'hi' } as IncomingMessage;

  const setup = (answer: unknown) => {
    const engine = {} as IWhatsAppEngine;
    const handleInboundMessage = jest.fn(() => answer);
    const host = { isLiveEngine: () => true, messages: { handleInboundMessage } } as unknown as SessionEngineWiringHost;
    const callbacks = new SessionEngineEventWiring({ logger: createLogger('test') }).buildCallbacks(
      'sess-1',
      engine,
      'sess-1-name',
      host,
    );
    return { callbacks, engine, handleInboundMessage };
  };

  it('answers the engine with the receipt the projector gave for the message', () => {
    const receipt = { settled: Promise.resolve({ conflict: true }) };
    const { callbacks, engine, handleInboundMessage } = setup(receipt);

    const returned = callbacks.onMessage?.(message);

    expect(returned).toBe(receipt);
    expect(handleInboundMessage).toHaveBeenCalledWith('sess-1', engine, message, undefined);
  });

  it('answers nothing when the projector commits nothing', () => {
    const { callbacks } = setup(undefined);

    expect(callbacks.onMessage?.(message)).toBeUndefined();
  });
});
