import type { Handle, HandleFetch } from '@sveltejs/kit';

const ENVOY = process.env.ENVOY_URL ?? 'http://envoy:8080';

export const handle: Handle = async ({ event, resolve }) => {
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url);

  if (url.pathname.startsWith('/api/v1/')) {
    const upstream = new URL(url.pathname + url.search, ENVOY);
    const traceId = crypto.randomUUID();
    const headers = new Headers(request.headers);
    // Forward cookies sent by the browser through SSR
    const cookie = event.request.headers.get('cookie');
    if (cookie) headers.set('cookie', cookie);
    headers.set('x-requested-with', 'oec-web');
    const requestBody = (request.body && request.headers.get('content-type')?.includes('application/json'))
      ? await request.clone().json().catch(() => null)
      : null;
    console.log('[ssr api proxy request]', {
      traceId,
      method: request.method,
      body: requestBody,
      from: url.pathname + url.search,
      to: upstream.toString(),
    });
    const response = await fetch(new Request(upstream, {
      method: request.method,
      headers,
      body: request.body,
      credentials: 'include',
      redirect: 'manual',
      // @ts-ignore - duplex is required in Node.js when body is a stream
      duplex: 'half'
    }));
    console.log('[ssr api proxy response]', {
      traceId,
      method: request.method,
      body: requestBody,
      from: url.pathname + url.search,
      to: upstream.toString(),
      status: response.status,
    });
    return response;
  }
  return fetch(request);
};
