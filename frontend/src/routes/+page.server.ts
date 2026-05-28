import type { PageServerLoad } from './$types';
import { getFeed, getMyInteractionsBatch, getUserPreferences } from '$lib/api';
import type { UserPreferences } from '$lib/types';

export const load: PageServerLoad = async ({ fetch, url, parent }) => {
  const feedParam = url.searchParams.get('feed');
  const feedMode: 'foryou' | 'following' = feedParam === 'following' ? 'following' : 'foryou';

  try {
    const modeParam = feedMode === 'following' ? 'following' : undefined;
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

    return { feed, me: me.items, feedMode, prefs };
  } catch {
    // Unauthenticated visit or feed-service down — render empty page.
    return { feed: null, me: {}, feedMode, prefs: null };
  }
};
