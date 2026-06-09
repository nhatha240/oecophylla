import { getPostsByTopic, getMyInteractionsBatch } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const topic = params.topic;
  try {
    const data = await getPostsByTopic(fetch, topic);
    // Hydrate the viewer's like/save state for the initial posts (batch endpoint
    // rejects an empty list, so guard on length).
    const ids = data.items.map((p) => p.id);
    const me = ids.length
      ? await getMyInteractionsBatch(fetch, ids).catch(() => ({ items: {} }))
      : { items: {} };
    return { topic, posts: data.items, nextCursor: data.next_cursor, me: me.items };
  } catch {
    return { topic, posts: [], nextCursor: null, me: {} };
  }
};
