import type { Handle, HandleFetch } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  return resolve(event);
};

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  return fetch(request);
};
