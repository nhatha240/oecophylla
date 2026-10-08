import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiFetch } from './api';
import { PREFERENCE_ACTION_EVENT } from './preferenceActions';

afterEach(() => vi.unstubAllGlobals());

describe('preference action refresh signal', () => {
  it('signals successful post interactions but not reads or failed writes', async () => {
    const window = new EventTarget();
    vi.stubGlobal('window', window);
    const listener = vi.fn();
    window.addEventListener(PREFERENCE_ACTION_EVENT, listener);
    const success = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const failure = vi.fn().mockResolvedValue(new Response('{"error":{"code":"FAILED"}}', { status: 500 }));

    await apiFetch(success as never, '/posts/post-1/like', { method: 'POST' });
    await apiFetch(success as never, '/posts/post-1/comments', { method: 'POST' });
    await apiFetch(success as never, '/posts/post-1', { method: 'GET' });
    await expect(apiFetch(failure as never, '/posts/post-1/save', { method: 'POST', quiet: true })).rejects.toBeDefined();

    expect(listener).toHaveBeenCalledTimes(2);
  });
});
