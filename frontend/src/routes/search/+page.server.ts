import type { PageServerLoad } from './$types';
import { getUserSuggestions, searchPosts, searchUsers } from '$lib/api';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const q = url.searchParams.get('q')?.trim() ?? '';
  const [posts, users] = q
    ? await Promise.all([searchPosts(fetch, q).catch(() => ({ items: [], next_cursor: null })), searchUsers(fetch, q).catch(() => ({ items: [] }))])
    : [{ items: [], next_cursor: null }, { items: await getUserSuggestions(fetch, 8).catch(() => []) }];
  return { q, posts: posts.items, users: users.items };
};
