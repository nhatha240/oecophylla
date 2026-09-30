import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/private', () => ({ env: { ENVOY_URL: 'http://envoy:8080' } }));

import { GET, POST } from './+server';

afterEach(() => vi.unstubAllGlobals());

function event(path: string, init: RequestInit = {}) {
  const url = new URL(`http://localhost:3000/api/v1/${path}`);
  return { request: new Request(url, init), url, params: { path } } as never;
}

describe('same-origin API proxy', () => {
  it('blocks cross-origin writes before contacting the API', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const response = await POST(event('posts', {
      method: 'POST', headers: { origin: 'https://attacker.example', 'content-type': 'application/json' }, body: '{}'
    }));
    expect(response.status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('forwards a same-origin write with the session cookie', async () => {
    const upstream = vi.fn().mockResolvedValue(new Response('{}'));
    vi.stubGlobal('fetch', upstream);
    const response = await POST(event('posts', {
      method: 'POST', headers: { origin: 'http://localhost:3000', cookie: 'oec_access=token' }, body: '{}'
    }));
    expect(response.status).toBe(200);
    expect(String(upstream.mock.calls[0][0])).toBe('http://envoy:8080/api/v1/posts');
    expect(new Headers(upstream.mock.calls[0][1].headers).get('cookie')).toBe('oec_access=token');
  });

  it('rejects a path that escapes the API prefix', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    const response = await GET(event('../admin/metrics'));
    expect(response.status).toBe(400);
    expect(upstream).not.toHaveBeenCalled();
  });
});
