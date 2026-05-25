import { describe, it, expect, vi } from 'vitest';
import { apiFetch, ApiException } from './api';

describe('apiFetch', () => {
  it('sends credentials and x-requested-with', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' }})
    );
    await apiFetch(fetchMock as unknown as typeof fetch, '/auth/me');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0]!;
    const init = call[1] as RequestInit;
    expect(init.credentials).toBe('include');
    expect((init.headers as Record<string, string>)['x-requested-with']).toBe('oec-web');
  });

  it('throws ApiException with envelope code on non-2xx', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ error: { code: 'CONFLICT', message: 'dup' }}), { status: 409, headers: { 'content-type': 'application/json' }}));
    await expect(apiFetch(fetchMock as any, '/x')).rejects.toMatchObject({ status: 409, code: 'CONFLICT' });
  });

  it('returns undefined on 204', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    const v = await apiFetch(fetchMock as any, '/logout', { method: 'DELETE' });
    expect(v).toBeUndefined();
  });
});
