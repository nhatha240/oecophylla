import { describe, expect, it } from 'vitest';
import { notificationActorName, notificationHref, notificationLabel, notificationPreview } from './notificationPresentation';
import type { Notification } from './types';

const liked: Notification = {
  id: 'notice-1', kind: 'liked', actor: { id: 'user-2', username: 'nguyen', display_name: 'Nguyễn Nguyên', avatar_url: null },
  post: { id: 'post-1', snippet: 'Bài viết của tôi' }, comment_id: null, payload: {}, read: false,
  created_at: '2026-10-08T02:00:00Z'
};

describe('notification presentation', () => {
  it('shows the actor and links a like to its post', () => {
    expect(notificationActorName(liked)).toBe('Nguyễn Nguyên');
    expect(notificationLabel(liked.kind)).toBe('đã thích bài viết của bạn');
    expect(notificationHref(liked)).toBe('/post/post-1');
    expect(notificationPreview(liked)).toBe('Bài viết của tôi');
  });

  it('shows comment text and links a comment to the discussion', () => {
    const commented: Notification = { ...liked, kind: 'commented', comment_id: 'comment-1', payload: { preview: 'Ý kiến rất hay' } };
    expect(notificationLabel(commented.kind)).toBe('đã bình luận về bài viết của bạn');
    expect(notificationHref(commented)).toBe('/post/post-1#comments');
    expect(notificationPreview(commented)).toBe('Ý kiến rất hay');
  });

  it('handles deleted actors and posts without a broken link', () => {
    const deleted: Notification = { ...liked, actor: null, post: null };
    expect(notificationActorName(deleted)).toBe('Một thành viên');
    expect(notificationHref(deleted)).toBeNull();
  });
});
