import type { RequestHandler } from '@sveltejs/kit';
import { proxyToEnvoy } from '$lib/server/proxy';

const handle: RequestHandler = async (event) => {
  const path = event.params.path ?? '';
  return proxyToEnvoy(event, `/api/v1/${path}`);
};

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
