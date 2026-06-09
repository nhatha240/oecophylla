import { getPostsByTag, getMyInteractionsBatch } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const tag = params.tag;
  try {
    const data = await getPostsByTag(fetch, tag);
    // Hydrate the viewer's like/save state for the initial posts (batch endpoint
    // rejects an empty list, so guard on length).
    const ids = data.items.map((p) => p.id);
    const me = ids.length
      ? await getMyInteractionsBatch(fetch, ids).catch(() => ({ items: {} }))
      : { items: {} };
    return { tag, posts: data.items, nextCursor: data.next_cursor, me: me.items };
  } catch {
    return { tag, posts: [], nextCursor: null, me: {} };
  }
};
