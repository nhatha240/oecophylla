import type { Post } from '$lib/types';
export const mockFeed: Post[] = Array.from({ length: 8 }).map((_, i) => ({
  id: `mock-${i}`, author_id: 'mock-author', content: `Đây là bài viết giả lập #${i + 1}.`,
  media_urls: [], tags: ['demo'], topics: ['tech'], safety_score: 1, status: 'published' as const,
  view_count: 100 + i, created_at: new Date(Date.now() - i * 3.6e6).toISOString(), updated_at: new Date().toISOString(),
}));
