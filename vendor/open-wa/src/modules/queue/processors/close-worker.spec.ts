import type { WorkerHost } from '@nestjs/bullmq';
import { closeWorkerIfStarted, MAX_WORKER_CLOSE_WAIT_MS } from './close-worker';

describe('closeWorkerIfStarted', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  const hungHost = (): WorkerHost =>
    ({ worker: { name: 'q', close: () => new Promise<void>(() => undefined) } }) as unknown as WorkerHost;

  const settledAt = async (waitMs: number): Promise<number> => {
    let doneAt = -1;
    const started = Date.now();
    void closeWorkerIfStarted(hungHost(), waitMs).then(() => (doneAt = Date.now() - started));
    await jest.advanceTimersByTimeAsync(MAX_WORKER_CLOSE_WAIT_MS + 1);
    return doneAt;
  };

  it('releases the hook at the requested wait when it is shorter than the cap', async () => {
    expect(await settledAt(2_000)).toBe(2_000);
  });

  it('clamps a longer wait to MAX_WORKER_CLOSE_WAIT_MS', async () => {
    expect(await settledAt(MAX_WORKER_CLOSE_WAIT_MS * 3)).toBe(MAX_WORKER_CLOSE_WAIT_MS);
  });

  it('settles a later worker.close() once the wait is over, as BullModule awaits it again', async () => {
    const host = hungHost();
    const pending = closeWorkerIfStarted(host, 1_000);
    await jest.advanceTimersByTimeAsync(1_000);
    await pending;
    await expect(host.worker.close()).resolves.toBeUndefined();
  });

  // A destroy hook that rejects makes Nest skip every hook after it (plugin onDisable, the usage flush).
  it('lets the teardown go on when the close rejects, and leaves the rejection to the later close', async () => {
    const failure = new Error('connection lost');
    const close = jest.fn().mockRejectedValue(failure);
    const worker = { name: 'q', close };

    await expect(closeWorkerIfStarted({ worker } as unknown as WorkerHost, 1_000)).resolves.toBeUndefined();

    expect(worker.close).toBe(close);
    await expect(worker.close()).rejects.toBe(failure);
  });

  it('leaves no timer running once the worker has closed', async () => {
    const host = { worker: { name: 'q', close: () => Promise.resolve() } } as unknown as WorkerHost;

    await closeWorkerIfStarted(host, MAX_WORKER_CLOSE_WAIT_MS);

    expect(jest.getTimerCount()).toBe(0);
  });
});
