import type { PageServerLoad } from './$types';
import { getFeed, getMyInteractionsBatch, getUserPreferences, getTrendingTopics } from '$lib/api';
import type { UserPreferences } from '$lib/types';

export const load: PageServerLoad = async ({ fetch, url, parent }) => {
  const feedParam = url.searchParams.get('feed');
  const feedMode: 'foryou' | 'following' | 'trending' =
    feedParam === 'following' || feedParam === 'trending' ? feedParam : 'foryou';
  const trendingTopics = await getTrendingTopics(fetch).catch(() => []);

  try {
    const modeParam = feedMode === 'foryou' ? undefined : feedMode;
    const feed = await getFeed(fetch, undefined, 20, modeParam);
    const postIds = feed.items.map((p) => p.id);
    const me = postIds.length
      ? await getMyInteractionsBatch(fetch, postIds).catch(() => ({ items: {} }))
      : { items: {} };

    const layout = await parent();
    const userId = layout.user?.id;
    const prefs: UserPreferences | null = userId
      ? await getUserPreferences(fetch, userId).catch(() => null)
      : null;

    return { feed, me: me.items, feedMode, prefs, trendingTopics };
  } catch {
    // Unauthenticated visit or feed-service down — render empty page.
    return { feed: null, me: {}, feedMode, prefs: null, trendingTopics };
  }
};
