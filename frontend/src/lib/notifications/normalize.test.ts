import { describe, expect, it } from 'vitest';
import {
  getNotificationActorInitial,
  getNotificationActorName,
  getNotificationHref,
  getNotificationSnippet,
  getNotificationType,
  isNotificationRead
} from './normalize';
import type { Notification } from '$lib/types';

describe('notification normalization', () => {
  it('handles backend-shaped actor notifications', () => {
    const item: Notification = {
      id: 'n1',
      kind: 'commented',
      actor: { id: 'u1', username: 'minhkhoa' },
      post: { id: 'p1', snippet: 'Bài viết mới' },
      read: false,
      created_at: new Date().toISOString()
    };

    expect(getNotificationType(item)).toBe('commented');
    expect(isNotificationRead(item)).toBe(false);
    expect(getNotificationActorName(item)).toBe('minhkhoa');
    expect(getNotificationActorInitial(item)).toBe('M');
    expect(getNotificationHref(item)).toBe('/post/p1');
    expect(getNotificationSnippet(item)).toBe('Bài viết mới');
  });

  it('handles actor-less system notifications without slicing undefined', () => {
    const item: Notification = {
      id: 'n2',
      kind: 'post_hidden',
      read: true,
      created_at: new Date().toISOString()
    };

    expect(getNotificationActorName(item)).toBe('Oecophylla');
    expect(getNotificationActorInitial(item)).toBe('O');
    expect(getNotificationHref(item)).toBe('/notifications');
    expect(isNotificationRead(item)).toBe(true);
  });
});
