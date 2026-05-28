import type { Handle, HandleFetch } from '@sveltejs/kit';

const ENVOY_URL = process.env.ENVOY_URL ?? 'http://envoy:8080';

export const handle: Handle = async ({ event, resolve }) => {
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/v1') || url.pathname.startsWith('/admin')) {
    const target = new URL(url.pathname + url.search, ENVOY_URL);
    const headers = new Headers();
    const cookie = event.request.headers.get('cookie');
    if (cookie) headers.set('cookie', cookie);
    const ct = request.headers.get('content-type');
    if (ct) headers.set('content-type', ct);
    const body = request.method !== 'GET' && request.method !== 'HEAD'
      ? await request.clone().text()
      : undefined;
    return fetch(target.toString(), { method: request.method, headers, body });
  }
  return fetch(request);
};
