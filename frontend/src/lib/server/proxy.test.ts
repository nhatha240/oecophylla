import { describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/private', () => ({
  env: {
    ENVOY_URL: 'http://localhost:8080'
  }
}));

import { proxyToEnvoy } from './proxy';

describe('proxyToEnvoy', () => {
  it('forwards request cookies and preserves upstream SSE headers', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect((init?.headers as Headers).get('cookie')).toBe('oec_access=token');
      expect((init?.headers as Headers).get('x-requested-with')).toBe('oec-web');

      return new Response('event: heartbeat\ndata: ping\n\n', {
        status: 200,
        headers: {
          'content-type': 'text/event-stream',
          'cache-control': 'no-store'
        }
      });
    });

    vi.stubGlobal('fetch', fetchMock);

    const event = {
      url: new URL('http://localhost:3000/api/v1/notifications/stream'),
      request: new Request('http://localhost:3000/api/v1/notifications/stream', {
        headers: {
          cookie: 'oec_access=token',
          accept: 'text/event-stream'
        }
      })
    };

    const response = await proxyToEnvoy(event as any, '/api/v1/notifications/stream');

    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('text/event-stream');
    expect(await response.text()).toContain('event: heartbeat');
  });
});
