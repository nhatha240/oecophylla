import type { Notification } from '$lib/types';

const SYSTEM_ACTOR = 'Oecophylla';

export function getNotificationType(item: Notification): string {
  return item.type ?? item.kind ?? 'notification';
}

export function isNotificationRead(item: Notification): boolean {
  return item.is_read ?? item.read ?? false;
}

export function getNotificationActorName(item: Notification): string {
  return (
    item.actor_display_name ??
    item.actor?.display_name ??
    item.actor_username ??
    item.actor?.username ??
    SYSTEM_ACTOR
  );
}

export function getNotificationActorInitial(item: Notification): string {
  return getNotificationActorName(item).trim().slice(0, 1).toUpperCase() || 'O';
}

export function getNotificationHref(item: Notification): string {
  const postId = item.post_id ?? item.post?.id ?? null;
  const actorId = item.actor_id ?? item.actor?.id ?? null;
  return postId ? `/post/${postId}` : actorId ? `/profile/${actorId}` : '/notifications';
}

export function getNotificationSnippet(item: Notification): string | null {
  return item.snippet ?? item.post?.snippet ?? null;
}
