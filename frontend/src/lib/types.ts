export type UserRole = 'user' | 'creator' | 'admin';
export type PostStatus = 'pending' | 'published' | 'hidden' | 'flagged';

export interface User { id: string; username: string; email: string; role: UserRole; display_name: string | null; avatar_url: string | null; }
export interface Profile extends User { bio: string | null; topic_prefs: string[]; created_at: string; }
export interface Post { id: string; author_id: string; content: string; media_urls: string[]; tags: string[]; topics: string[]; safety_score: number; status: PostStatus; view_count: number; created_at: string; updated_at: string; }
export interface ApiError { error: { code: string; message: string; details?: unknown }; }
