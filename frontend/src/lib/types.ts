export type UserRole = 'user' | 'creator' | 'admin';
export type PostStatus = 'pending' | 'published' | 'hidden' | 'flagged';
export type ReportReason = 'spam' | 'misinformation' | 'harassment' | 'nsfw' | 'other';

export interface User { id: string; username: string; email: string; role: UserRole; display_name: string | null; avatar_url: string | null; }
export interface Profile extends User { bio: string | null; topic_prefs: string[]; created_at: string; }
export interface Post { id: string; author_id: string; content: string; media_urls: string[]; tags: string[]; topics: string[]; safety_score: number; status: PostStatus; view_count: number; like_count: number; comment_count: number; save_count: number; share_count: number; created_at: string; updated_at: string; }
export interface Comment { id: string; post_id: string; author_id: string; author_username: string; author_display_name: string | null; parent_comment_id: string | null; content: string; is_deleted: boolean; created_at: string; replies?: Comment[]; reply_count?: number; has_more_replies?: boolean; }
export interface MyInteractions { liked: boolean; saved: boolean; shared: boolean; hidden: boolean; reported_pending: boolean; }
export interface ApiError { error: { code: string; message: string; details?: unknown }; }

export type FeedSource = 'cache' | 'personalized' | 'fallback';
export interface FeedRank { score: number; source: string; reason: string; }
export interface FeedItem extends Post {
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  rank: FeedRank;
}
export interface FeedResponse {
  items: FeedItem[];
  next_cursor: string | null;
  source: FeedSource;
  generated_at: string;
}
export interface BatchMeResponse { items: Record<string, MyInteractions>; }

export type NotificationType =
  | 'liked'
  | 'commented'
  | 'comment_replied'
  | 'followed'
  | 'post_hidden'
  | 'author_warned'
  | 'author_banned'
  | 'report_dismissed';

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  actor_id: string;
  post_id?: string | null;
  comment_id?: string | null;
  is_read: boolean;
  created_at: string;
  actor_username: string;
  actor_display_name: string | null;
  snippet?: string | null;
}

export interface NotificationListResponse {
  items: Notification[];
  next_cursor: string | null;
}

export type ModerationAction = 'dismiss' | 'hide_post' | 'warn_author' | 'ban_author';

export interface AdminReport {
  id: string;
  post_id: string;
  reporter_id: string;
  reason: ReportReason;
  detail?: string | null;
  status: string;
  created_at: string;
  updated_at?: string;
  post_snippet?: string | null;
  reporter_username?: string | null;
  reporter_display_name?: string | null;
  author_id?: string | null;
  author_username?: string | null;
  author_display_name?: string | null;
}

export interface AdminAuditLog {
  id: string;
  actor_id: string;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  actor_username?: string | null;
  actor_display_name?: string | null;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}
