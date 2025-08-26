import { fetchJsonWithRetry } from './retry';

describe('fetchJsonWithRetry', () => {
  const originalFetch = global.fetch as any;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  it('retries on 500 and succeeds', async () => {
    jest.useFakeTimers();
    const calls: number[] = [];
    global.fetch = jest.fn(async () => {
      calls.push(Date.now());
      if (calls.length < 2) {
        return { ok: false, status: 500, text: async () => 'err' } as any;
      }
      return { ok: true, json: async () => ({ ok: true }) } as any;
    });

    const p = fetchJsonWithRetry<any>(
      'http://example.com',
      { method: 'GET' },
      { backoffBaseMs: 1 }
    );
    // advance timers to allow retry backoff
    await Promise.resolve();
    jest.advanceTimersByTime(2);
    const res = await p;
    expect(res.ok).toBe(true);
    expect((global.fetch as any).mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
