import type { AdminAuditLog, AdminReport, ApiError, BatchMeResponse, CursorPage, DashboardMetrics, FeedResponse, ModerationAction, PostListResponse, ResolveResponse, SavedPostResponse, SearchPostResponse, SearchUserResponse } from './types';

export class ApiException extends Error {
  constructor(public status: number, public code: string, public details?: unknown) {
    super(`${status} ${code}`);
  }
}

export type Fetch = typeof fetch;
export type ApiFetchInit = RequestInit & { quiet?: boolean };

const refreshLocks = new WeakMap<Fetch, Promise<boolean>>();

function getTarget(path: string): string {
  // Admin routes go directly to moderation-service via envoy (/admin/* → moderation_cluster).
  // Non-admin routes go through the /api/v1 prefix.
  return path.startsWith('/admin')
    ? path
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
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export async function getFeed(fetcher: Fetch, cursor?: string, limit = 20, mode?: string): Promise<FeedResponse> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  if (mode) qs.set('mode', mode);
  return apiFetch<FeedResponse>(fetcher, `/feed?${qs}`);
}

export async function getMyInteractionsBatch(fetcher: Fetch, postIds: string[]): Promise<BatchMeResponse> {
  return apiFetch<BatchMeResponse>(fetcher, '/interactions/me/batch', {
    method: 'POST',
    body: JSON.stringify({ post_ids: postIds }),
  });
}

export async function getPostsByTag(fetcher: Fetch, tag: string, cursor?: string, limit = 20): Promise<PostListResponse> {
  const qs = new URLSearchParams({ tag, limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<PostListResponse>(fetcher, `/posts?${qs}`);
}

export async function getPostsByTopic(fetcher: Fetch, topic: string, cursor?: string, limit = 20): Promise<PostListResponse> {
  const qs = new URLSearchParams({ topic, limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<PostListResponse>(fetcher, `/posts?${qs}`);
}

export async function getSavedPosts(fetcher: Fetch, cursor?: string, limit = 20): Promise<SavedPostResponse> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<SavedPostResponse>(fetcher, `/posts/saved?${qs}`);
}

export async function searchPosts(fetcher: Fetch, q: string, cursor?: string, limit = 20): Promise<SearchPostResponse> {
  const qs = new URLSearchParams({ q, type: 'post', limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<SearchPostResponse>(fetcher, `/search?${qs}`);
}

export async function searchUsers(fetcher: Fetch, q: string, limit = 20): Promise<SearchUserResponse> {
  const qs = new URLSearchParams({ q, limit: String(limit) });
  return apiFetch<SearchUserResponse>(fetcher, `/users?${qs}`);
}

export interface SuggestionItem {
  id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  mutual_count: number;
}

export async function getUserSuggestions(fetcher: Fetch, limit = 5): Promise<SuggestionItem[]> {
  return apiFetch<SuggestionItem[]>(fetcher, `/users/suggestions?limit=${limit}`);
}

export async function followUser(fetcher: Fetch, userId: string): Promise<void> {
  return apiFetch(fetcher, `/users/${userId}/follow`, { method: 'POST' });
}

export async function unfollowUser(fetcher: Fetch, userId: string): Promise<void> {
  return apiFetch(fetcher, `/users/${userId}/follow`, { method: 'DELETE' });
}

export async function getAdminReports(fetcher: Fetch, params: { status?: string; cursor?: string; limit?: number } = {}): Promise<CursorPage<AdminReport>> {
  const qs = new URLSearchParams({ limit: String(params.limit ?? 20) });
  if (params.status) qs.set('status', params.status);
  if (params.cursor) qs.set('cursor', params.cursor);
  return apiFetch<CursorPage<AdminReport>>(fetcher, `/admin/reports?${qs}`);
}

export async function resolveReport(fetcher: Fetch, reportId: string, action: ModerationAction, note?: string): Promise<ResolveResponse> {
  return apiFetch<ResolveResponse>(fetcher, `/admin/reports/${reportId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action, note: note || undefined }),
  });
}

export async function getAuditLog(fetcher: Fetch, params: { cursor?: string; limit?: number; actor_id?: string; action?: string } = {}): Promise<CursorPage<AdminAuditLog>> {
  const qs = new URLSearchParams({ limit: String(params.limit ?? 20) });
  if (params.cursor) qs.set('cursor', params.cursor);
  if (params.actor_id) qs.set('actor_id', params.actor_id);
  if (params.action) qs.set('action', params.action);
  return apiFetch<CursorPage<AdminAuditLog>>(fetcher, `/admin/audit-logs?${qs}`);
}

export async function getAdminMetrics(fetcher: Fetch): Promise<DashboardMetrics> {
  return apiFetch<DashboardMetrics>(fetcher, '/admin/metrics');
}

export async function changePassword(fetcher: Fetch, body: { current_password: string; new_password: string }): Promise<void> {
  return apiFetch(fetcher, '/auth/password', { method: 'PUT', body: JSON.stringify(body) });
}

export async function deleteAccount(fetcher: Fetch, body: { password: string }): Promise<void> {
  return apiFetch(fetcher, '/auth/account', { method: 'DELETE', body: JSON.stringify(body) });
}
