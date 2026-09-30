import type { Handle, HandleFetch } from '@sveltejs/kit';

const API_ENDPOINT = process.env.ENVOY_URL ?? process.env.API_ENDPOINT ?? 'http://envoy:8080';

export const handle: Handle = async ({ event, resolve }) => {
  if (!['GET', 'HEAD', 'OPTIONS'].includes(event.request.method)) {
    const origin = event.request.headers.get('origin');
    const fetchSite = event.request.headers.get('sec-fetch-site');
    if ((origin && origin !== event.url.origin) || fetchSite === 'cross-site') {
      return new Response('Forbidden', { status: 403 });
    }
  }
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url);
  if (url.origin === event.url.origin && (url.pathname.startsWith('/api/v1/') || url.pathname.startsWith('/admin/'))) {
    const target = new URL(url.pathname + url.search, API_ENDPOINT);
    const headers = new Headers();
    const cookie = request.headers.get('cookie') ?? event.request.headers.get('cookie');
    if (cookie) headers.set('cookie', cookie);
    const ct = request.headers.get('content-type');
    if (ct) headers.set('content-type', ct);
    const body = request.method !== 'GET' && request.method !== 'HEAD'
      ? await request.clone().arrayBuffer()
      : undefined;
    return fetch(target.toString(), { method: request.method, headers, body });
  }
  return fetch(request);
};
