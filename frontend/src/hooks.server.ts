import type { Handle, HandleFetch } from '@sveltejs/kit';

const ENVOY = process.env.ENVOY_URL ?? 'http://envoy:8080';

export const handle: Handle = async ({ event, resolve }) => {
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/v1/')) {
    const upstream = new URL(url.pathname + url.search, ENVOY);
    const headers = new Headers(request.headers);
    // Forward cookies sent by the browser through SSR
    const cookie = event.request.headers.get('cookie');
    if (cookie) headers.set('cookie', cookie);
    headers.set('x-requested-with', 'oec-web');
    return fetch(new Request(upstream, { method: request.method, headers, body: request.body, credentials: 'include', redirect: 'manual' }));
  }
  return fetch(request);
};
