import type { PageLoad } from './$types';
import { searchPosts, searchUsers } from '$lib/api';

export const load: PageLoad = async ({ url, fetch }) => {
  const q = url.searchParams.get('q') ?? '';
  const type = url.searchParams.get('type') ?? 'post';

  if (!q.trim()) {
    return { q, type, posts: null, users: null };
  }

  if (type === 'user') {
    try {
      const users = await searchUsers(fetch, q);
      return { q, type, posts: null, users };
    } catch {
      return { q, type, posts: null, users: { items: [] } };
    }
  }

  try {
    const posts = await searchPosts(fetch, q);
    return { q, type, posts, users: null };
  } catch {
    return { q, type, posts: { items: [], next_cursor: null }, users: null };
  }
};
