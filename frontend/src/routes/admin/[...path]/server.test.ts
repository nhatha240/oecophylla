import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/private', () => ({ env: { ENVOY_URL: 'http://envoy:8080' } }));

import { GET, POST } from './+server';

afterEach(() => vi.unstubAllGlobals());

function event(path: string, role?: string, init: RequestInit = {}) {
  const url = new URL(`http://localhost:3000/admin/${path}`);
  const fetch = vi.fn().mockResolvedValue(role
    ? Response.json({ user: { role } })
    : new Response(null, { status: 401 }));
  return { event: { request: new Request(url, init), url, params: { path }, fetch } as never, fetch };
}

describe('admin API proxy', () => {
  it('rejects requests without a session', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const { event: requestEvent } = event('metrics');
    expect((await GET(requestEvent)).status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('rejects a normal user', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const { event: requestEvent } = event('metrics', 'user');
    expect((await GET(requestEvent)).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('forwards an admin request to moderation', async () => {
    const upstream = vi.fn().mockResolvedValue(Response.json({ total_posts: 5 }));
    vi.stubGlobal('fetch', upstream);
    const { event: requestEvent } = event('metrics', 'admin');
    expect((await GET(requestEvent)).status).toBe(200);
    expect(String(upstream.mock.calls[0][0])).toBe('http://envoy:8080/admin/metrics');
  });

  it('rejects a cross-origin admin write', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const { event: requestEvent } = event('reports/id/resolve', 'admin', {
      method: 'POST', headers: { origin: 'https://attacker.example' }, body: '{}'
    });
    expect((await POST(requestEvent)).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });
});
