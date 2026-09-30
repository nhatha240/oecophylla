import { describe, expect, it, vi } from 'vitest';
import type { Handle, HandleFetch } from '@sveltejs/kit';
import { handle, handleFetch } from './hooks.server';

async function invoke(request: Request) {
  const upstream = vi.fn<typeof fetch>().mockResolvedValue(new Response('{}'));
  const event = {
    url: new URL('http://localhost:3000/settings'),
    request: new Request('http://localhost:3000/settings', {
      headers: { cookie: 'oec_access=test-token' }
    })
  };
  await handleFetch({ event, request, fetch: upstream } as unknown as Parameters<HandleFetch>[0]);
  return upstream;
}

describe('server API fetch hook', () => {
  it.each(['GET', 'HEAD'])('forwards %s with cookies and no body', async (method) => {
    const upstream = await invoke(new Request('http://localhost:3000/api/v1/auth/me?fresh=1', { method }));
    const [url, init] = upstream.mock.calls[0];
    expect(String(url)).toBe('http://envoy:8080/api/v1/auth/me?fresh=1');
    expect(init?.method).toBe(method);
    expect(new Headers(init?.headers).get('cookie')).toBe('oec_access=test-token');
    expect(init?.body).toBeUndefined();
  });

  it.each(['POST', 'PUT', 'PATCH', 'DELETE'])('preserves %s payload bytes', async (method) => {
    const bytes = new Uint8Array([0, 255, 128, 65]);
    const upstream = await invoke(new Request('http://localhost:3000/api/v1/users/u/avatar', {
      method, body: bytes, headers: { 'content-type': 'application/octet-stream' }
    }));
    const init = upstream.mock.calls[0][1];
    expect(new Uint8Array(await new Response(init?.body).arrayBuffer())).toEqual(bytes);
    expect(new Headers(init?.headers).get('content-type')).toBe('application/octet-stream');
  });

  it('leaves unrelated fetches unchanged', async () => {
    const request = new Request('https://example.test/resource');
    const upstream = await invoke(request);
    expect(upstream).toHaveBeenCalledWith(request);
  });

  it('keeps an explicit rotated cookie for the current-user retry', async () => {
    const upstream = await invoke(new Request('http://localhost:3000/api/v1/auth/me', {
      headers: { cookie: 'oec_access=rotated-token' }
    }));
    expect(new Headers(upstream.mock.calls[0][1]?.headers).get('cookie')).toBe('oec_access=rotated-token');
  });
});

describe('incoming request origin guard', () => {
  it('rejects a cross-origin form before reaching the action', async () => {
    const resolve = vi.fn().mockResolvedValue(new Response('ok'));
    const url = new URL('http://localhost:3000/login');
    const request = new Request(url, {
      method: 'POST',
      headers: { origin: 'https://attacker.example', 'content-type': 'application/x-www-form-urlencoded' },
      body: 'email_or_username=x&password=y'
    });
    const response = await handle({ event: { url, request }, resolve } as unknown as Parameters<Handle>[0]);
    expect(response.status).toBe(403);
    expect(resolve).not.toHaveBeenCalled();
  });

  it('allows a same-origin write', async () => {
    const resolve = vi.fn().mockResolvedValue(new Response('ok'));
    const url = new URL('http://localhost:3000/login');
    const request = new Request(url, { method: 'POST', headers: { origin: url.origin }, body: '' });
    const response = await handle({ event: { url, request }, resolve } as unknown as Parameters<Handle>[0]);
    expect(response.status).toBe(200);
    expect(resolve).toHaveBeenCalledOnce();
  });
});
