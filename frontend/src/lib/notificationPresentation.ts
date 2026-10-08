import type { Notification, NotificationType } from './types';

const labels: Record<NotificationType, string> = {
  liked: 'đã thích bài viết của bạn',
  commented: 'đã bình luận về bài viết của bạn',
  replied: 'đã trả lời bình luận của bạn',
  followed: 'đã theo dõi bạn',
  post_hidden: 'bài viết đã được ẩn',
  author_warned: 'tài khoản nhận cảnh báo',
  author_banned: 'tài khoản đã bị hạn chế',
  report_dismissed: 'báo cáo đã được xử lý'
};

export function notificationLabel(kind: NotificationType): string {
  return labels[kind] ?? 'có cập nhật mới';
}

export function notificationActorName(notice: Notification): string {
  return notice.actor?.display_name || notice.actor?.username || 'Một thành viên';
}

export function notificationHref(notice: Notification): string | null {
  if (notice.post) return `/post/${notice.post.id}${notice.comment_id ? '#comments' : ''}`;
  if (notice.actor && notice.kind === 'followed') return `/profile/${notice.actor.id}`;
  return null;
}

export function notificationPreview(notice: Notification): string | null {
  return notice.payload?.preview || notice.post?.snippet || null;
}
