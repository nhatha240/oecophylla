import type { PageServerLoad } from './$types';
import { getFeed, getMyInteractionsBatch } from '$lib/api';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const feedParam = url.searchParams.get('feed');
  const feedMode: 'foryou' | 'following' = feedParam === 'following' ? 'following' : 'foryou';

  try {
    const modeParam = feedMode === 'following' ? 'following' : undefined;
    const feed = await getFeed(fetch, undefined, 20, modeParam);
    const postIds = feed.items.map((p) => p.id);
    const me = postIds.length
      ? await getMyInteractionsBatch(fetch, postIds).catch(() => ({ items: {} }))
      : { items: {} };
    return { feed, me: me.items, feedMode };
  } catch {
    // Unauthenticated visit or feed-service down — render empty page.
    return { feed: null, me: {}, feedMode };
  }
};
