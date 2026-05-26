import type { PageServerLoad } from './$types';
import { getFeed, getMyInteractionsBatch } from '$lib/api';

export const load: PageServerLoad = async ({ fetch }) => {
  try {
    const feed = await getFeed(fetch, undefined, 20);
    const postIds = feed.items.map((p) => p.id);
    const me = postIds.length
      ? await getMyInteractionsBatch(fetch, postIds).catch(() => ({ items: {} }))
      : { items: {} };
    return { feed, me: me.items };
  } catch {
    // Unauthenticated visit or feed-service down — render empty page.
    return { feed: null, me: {} };
  }
};
