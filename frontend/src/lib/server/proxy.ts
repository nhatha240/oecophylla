import type { RequestEvent } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

function withBody(method: string): boolean {
  return !['GET', 'HEAD'].includes(method.toUpperCase());
}

export async function proxyToEnvoy(event: RequestEvent, upstreamPath: string): Promise<Response> {
  const envoy = env.ENVOY_URL ?? 'http://localhost:8080';
  const upstreamUrl = new URL(upstreamPath + event.url.search, envoy);
  const headers = new Headers(event.request.headers);
  const cookie = event.request.headers.get('cookie');

  headers.delete('host');
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
