import { redirect, type ServerLoad } from '@sveltejs/kit';
import { getSavedPosts, getMyInteractionsBatch, ApiException } from '$lib/api';

export const load: ServerLoad = async ({ fetch, parent }) => {
  const { user } = await parent();
  if (!user) throw redirect(303, '/login');

  try {
    const saved = await getSavedPosts(fetch);
    const postIds = saved.items.map((p) => p.id);
    const me = postIds.length
      ? await getMyInteractionsBatch(fetch, postIds).catch(() => ({ items: {} }))
      : { items: {} };
    return { saved, me: me.items };
  } catch (e) {
    if (e instanceof ApiException && e.status === 401) throw redirect(303, '/login');
    console.error('[saved] load error:', e);
    return { saved: { items: [], next_cursor: null }, me: {} };
  }
};
