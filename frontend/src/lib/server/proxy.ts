import type { RequestEvent } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

function withBody(method: string): boolean {
  return !['GET', 'HEAD'].includes(method.toUpperCase());
}

// Hop-by-hop headers must not be forwarded via fetch() — they are connection-level
// and Node.js fetch will throw TypeError if they're present.
const HOP_BY_HOP = [
  'connection',
  'keep-alive',
  'transfer-encoding',
  'upgrade',
  'proxy-authorization',
  'proxy-authenticate',
  'te',
  'trailer',
];

export async function proxyToEnvoy(event: RequestEvent, upstreamPath: string): Promise<Response> {
  const envoy = env.ENVOY_URL ?? 'http://localhost:8080';
  const upstreamUrl = new URL(upstreamPath + event.url.search, envoy);
  const headers = new Headers(event.request.headers);
  const cookie = event.request.headers.get('cookie');

  headers.delete('host');
  for (const h of HOP_BY_HOP) headers.delete(h);
  if (cookie) headers.set('cookie', cookie);
  headers.set('x-requested-with', 'oec-web');

  const response = await fetch(upstreamUrl, {
    method: event.request.method,
    headers,
    body: withBody(event.request.method) ? event.request.body : undefined,
    redirect: 'manual',
    // @ts-expect-error Node.js requires duplex when streaming the incoming body.
    duplex: withBody(event.request.method) ? 'half' : undefined
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers
  });
}
