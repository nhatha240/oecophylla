import type { PageServerLoad } from './$types';
import { searchPosts, searchUsers, getTrendingTopics, getFeed, getMyInteractionsBatch } from '$lib/api';

export const load: PageServerLoad = async ({ url, fetch }) => {
  const q = url.searchParams.get('q') ?? '';
  // A leading "@" is an explicit user lookup (e.g. "@quynhanh") regardless of
  // the active tab; the "@" is stripped before querying.
  const isMention = q.trim().startsWith('@');
  const mentionQuery = q.trim().replace(/^@+/, '').trim();
  const type = isMention ? 'user' : (url.searchParams.get('type') ?? 'post');
  const filter = url.searchParams.get('filter') ?? 'all';

  // Hydrate the viewer's like/save state for a set of posts so they render with
  // the correct (red) like color. The batch endpoint rejects an empty list.
  const hydrateMe = async (ids: string[]): Promise<Record<string, unknown>> =>
    ids.length
      ? (await getMyInteractionsBatch(fetch, ids).catch(() => ({ items: {} }))).items
      : {};

  // When no query (or a bare "@") → explore/discovery mode
  if (!q.trim() || (isMention && !mentionQuery)) {
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
    const me = await hydrateMe(featuredPosts.map((p) => p.id));

    return {
      q, type, filter,
      mode: 'explore' as const,
      trendingTopics,
      featuredPosts,
      creators,
      posts: null, users: null,
      me,
    };
  }

  // Query mode → search results
  if (type === 'user') {
    const userQuery = isMention ? mentionQuery : q;
    try {
      const users = await searchUsers(fetch, userQuery);
      return { q, type, filter, mode: 'search' as const, posts: null, users, trendingTopics: [], featuredPosts: [], creators: [] };
    } catch {
      return { q, type, filter, mode: 'search' as const, posts: null, users: { items: [] }, trendingTopics: [], featuredPosts: [], creators: [] };
    }
  }

  try {
    const posts = await searchPosts(fetch, q);
    const me = await hydrateMe(posts.items.map((p) => p.id));
    return { q, type, filter, mode: 'search' as const, posts, users: null, trendingTopics: [], featuredPosts: [], creators: [], me };
  } catch {
    return { q, type, filter, mode: 'search' as const, posts: { items: [], next_cursor: null }, users: null, trendingTopics: [], featuredPosts: [], creators: [], me: {} };
  }
};
