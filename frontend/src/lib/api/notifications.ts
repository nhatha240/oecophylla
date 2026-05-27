import { apiFetch, type Fetch } from '$lib/api';
import type { NotificationListResponse } from '$lib/types';

export async function listNotifications(
  fetchImpl: Fetch,
  params: { cursor?: string; limit?: number; unread_only?: boolean } = {}
): Promise<NotificationListResponse> {
  const qs = new URLSearchParams();
  qs.set('limit', String(params.limit ?? 20));
  if (params.cursor) qs.set('cursor', params.cursor);
  if (params.unread_only) qs.set('unread_only', 'true');
  return apiFetch<NotificationListResponse>(fetchImpl, `/notifications?${qs.toString()}`, { quiet: true });
}

export async function markNotificationRead(fetchImpl: Fetch, id: string): Promise<void> {
  await apiFetch<void>(fetchImpl, `/notifications/${id}/read`, { method: 'POST', quiet: true });
}

export async function markAllNotificationsRead(fetchImpl: Fetch): Promise<void> {
  await apiFetch<void>(fetchImpl, '/notifications/read-all', { method: 'POST', quiet: true });
}

export async function getNotificationUnreadCount(fetchImpl: Fetch): Promise<{ count: number }> {
  return apiFetch<{ count: number }>(fetchImpl, '/notifications/unread-count', { quiet: true });
}
