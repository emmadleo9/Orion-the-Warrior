// A contact's status items all mount at once. The gateway answers a route ten times a second per IP and
// refuses the rest with a 429, so fetching every item together left the newest ones as "Media unavailable"
// for good; they take their turns now, and a refusal that still arrives is retried.
import '../../test-helpers/register-hooks.ts';
import { test, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';

type RTL = typeof import('@testing-library/react');

let rtl: RTL;
let StatusMedia: typeof import('./StatusMedia.tsx').default;
let sessionApi: typeof import('../../services/api.ts').sessionApi;

before(async () => {
  const { installJsdomGlobals } = await import('../../test-helpers/jsdom.ts');
  await installJsdomGlobals();
  const { i18nReady } = await import('../../i18n/index.ts');
  await i18nReady;
  rtl = await import('@testing-library/react');
  ({ default: StatusMedia } = await import('./StatusMedia.tsx'));
  ({ sessionApi } = await import('../../services/api.ts'));
  URL.createObjectURL = (): string => 'blob:status';
  URL.revokeObjectURL = (): void => undefined;
});

afterEach(() => rtl.cleanup());

test('twelve status items mounted together all end up with their media when the gateway refuses past ten a second', async () => {
  const startedAt: number[] = [];
  const api = sessionApi as unknown as {
    getStatusMediaBlob: (id: string, statusId: string, signal?: AbortSignal) => Promise<Blob>;
  };
  const original = api.getStatusMediaBlob;
  api.getStatusMediaBlob = () => {
    const now = Date.now();
    startedAt.push(now);
    const inWindow = startedAt.filter(t => now - t < 1000).length;
    return inWindow > 10
      ? Promise.reject(Object.assign(new Error('Too Many Requests'), { status: 429 }))
      : Promise.resolve(new Blob(['x'], { type: 'image/jpeg' }));
  };
  try {
    const { container } = rtl.render(
      createElement(
        'div',
        null,
        Array.from({ length: 12 }, (_, i) =>
          createElement(StatusMedia, { key: i, sessionId: 's1', statusId: `st-${i}`, type: 'image' as const }),
        ),
      ),
    );

    await rtl.waitFor(
      () => {
        assert.equal(container.querySelectorAll('img.channel-media').length, 12);
      },
      { timeout: 6000 },
    );
    assert.equal(container.querySelectorAll('.status-media-placeholder').length, 0);
  } finally {
    api.getStatusMediaBlob = original;
  }
});
