import type { RequestHandler } from './$types';
import { proxyToEnvoy } from '$lib/server/upstreamProxy';

const handle: RequestHandler = async ({ request, params, url }) => {
  return proxyToEnvoy(request, url, '/api/v1/' + (params.path ?? ''), '/api/v1/');
};

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
