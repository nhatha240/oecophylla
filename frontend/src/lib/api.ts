import type { ApiError, BatchMeResponse, FeedResponse } from './types';

export class ApiException extends Error {
  constructor(public status: number, public code: string, public details?: unknown) {
    super(`${status} ${code}`);
  }
}

export type Fetch = typeof fetch;
export type ApiFetchInit = RequestInit & { quiet?: boolean };

export async function apiFetch<T>(fetchImpl: Fetch, path: string, init: ApiFetchInit = {}): Promise<T> {
  const target = path.startsWith('/admin')
    ? `/api/v1/admin${path.slice('/admin'.length)}`
    : `/api/v1${path}`;
  const res = await fetchImpl(target, {
    credentials: 'include',
    headers: {
      'content-type': 'application/json',
      'x-requested-with': 'oec-web',
      ...(init.headers || {}),
    },
    ...init,
  });
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
