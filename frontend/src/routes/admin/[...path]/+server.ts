import type { RequestHandler } from './$types';
import { proxyToEnvoy } from '$lib/server/upstreamProxy';

const handle: RequestHandler = async ({ request, params, url, fetch }) => {
  const identity = await fetch('/api/v1/auth/me');
  if (!identity.ok) return new Response('Unauthorized', { status: 401 });
  const { user } = await identity.json() as { user?: { role?: string } };
  if (user?.role !== 'admin') return new Response('Forbidden', { status: 403 });
  return proxyToEnvoy(request, url, '/admin/' + (params.path ?? ''), '/admin/');
};

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
