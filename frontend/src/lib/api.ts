import type { ApiError, BatchMeResponse, FeedResponse } from './types';

export class ApiException extends Error {
  constructor(public status: number, public code: string, public details?: unknown) {
    super(`${status} ${code}`);
  }
}

export type Fetch = typeof fetch;
export type ApiFetchInit = RequestInit & { quiet?: boolean };

const refreshLocks = new WeakMap<Fetch, Promise<boolean>>();

function getTarget(path: string): string {
  return path.startsWith('/admin')
    ? `/api/v1/admin${path.slice('/admin'.length)}`
    : `/api/v1${path}`;
}

function withDefaultHeaders(init: ApiFetchInit): RequestInit {
  return {
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      'x-requested-with': 'oec-web',
      ...(init.headers || {}),
    },
    ...init,
  };
}

function canRefresh(path: string): boolean {
  return !path.startsWith('/auth/login')
    && !path.startsWith('/auth/register')
    && !path.startsWith('/auth/logout')
    && !path.startsWith('/auth/refresh');
}

export async function refreshSession(fetchImpl: Fetch): Promise<boolean> {
  const inFlight = refreshLocks.get(fetchImpl);
  if (inFlight) return inFlight;

  const refreshPromise = (async () => {
    const response = await fetchImpl('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'x-requested-with': 'oec-web',
      },
    });
    return response.ok;
  })();

  refreshLocks.set(fetchImpl, refreshPromise);

  try {
    return await refreshPromise;
  } finally {
    refreshLocks.delete(fetchImpl);
  }
}

export async function apiFetch<T>(
  fetchImpl: Fetch,
  path: string,
  init: ApiFetchInit = {},
  allowRefresh = true
): Promise<T> {
  const target = getTarget(path);
  const res = await fetchImpl(target, withDefaultHeaders(init));

  if (res.status === 401 && allowRefresh && canRefresh(path) && await refreshSession(fetchImpl)) {
    return apiFetch<T>(fetchImpl, path, init, false);
  }

  if (!res.ok) {
    let body: ApiError | null = null;
    try { body = await res.json(); } catch { /* ignore parse errors */ }
    if (!init.quiet) console.error('API error', { path, status: res.status, body });
    throw new ApiException(res.status, body?.error.code ?? 'UNKNOWN', body?.error.details);
  }
  if (res.status === 204) return undefined as T;
  return await res.json() as T;
}

export async function getFeed(fetcher: Fetch, cursor?: string, limit = 20): Promise<FeedResponse> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<FeedResponse>(fetcher, `/feed?${qs}`);
}

export async function getMyInteractionsBatch(fetcher: Fetch, postIds: string[]): Promise<BatchMeResponse> {
  return apiFetch<BatchMeResponse>(fetcher, '/interactions/me/batch', {
    method: 'POST',
    body: JSON.stringify({ post_ids: postIds }),
  });
}
