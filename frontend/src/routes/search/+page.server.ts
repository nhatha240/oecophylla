import type { PageServerLoad } from './$types';
import { searchPosts, searchUsers, getTrendingTopics, getFeed } from '$lib/api';

export const load: PageServerLoad = async ({ url, fetch }) => {
  const q = url.searchParams.get('q') ?? '';
  const type = url.searchParams.get('type') ?? 'post';
  const filter = url.searchParams.get('filter') ?? 'all';

  // When no query → explore/discovery mode
  if (!q.trim()) {
    const [topicsResult, featuredResult, creatorsResult] = await Promise.allSettled([
      getTrendingTopics(fetch),
      getFeed(fetch, undefined, 6),
      searchUsers(fetch, 'seed', 8),
    ]);

    const trendingTopics = topicsResult.status === 'fulfilled' ? topicsResult.value : [];
    const featuredPosts = featuredResult.status === 'fulfilled' ? featuredResult.value.items : [];
    const creators = creatorsResult.status === 'fulfilled'
      ? creatorsResult.value.items.filter((u) => u.role === 'creator').slice(0, 4)
      : [];

    return {
      q, type, filter,
      mode: 'explore' as const,
      trendingTopics,
      featuredPosts,
      creators,
      posts: null, users: null,
    };
  }

  // Query mode → search results
  if (type === 'user') {
    try {
      const users = await searchUsers(fetch, q);
      return { q, type, filter, mode: 'search' as const, posts: null, users, trendingTopics: [], featuredPosts: [], creators: [] };
    } catch {
      return { q, type, filter, mode: 'search' as const, posts: null, users: { items: [] }, trendingTopics: [], featuredPosts: [], creators: [] };
    }
  }

  try {
    const posts = await searchPosts(fetch, q);
    return { q, type, filter, mode: 'search' as const, posts, users: null, trendingTopics: [], featuredPosts: [], creators: [] };
  } catch {
    return { q, type, filter, mode: 'search' as const, posts: { items: [], next_cursor: null }, users: null, trendingTopics: [], featuredPosts: [], creators: [] };
  }
};
