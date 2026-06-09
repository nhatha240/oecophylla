import type { PageServerLoad } from './$types';
import { apiFetch, ApiException, getMyInteractionsBatch } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Profile, PostListResponse } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch, request }) => {
  const cookie = request.headers.get('cookie') ?? '';
  const authedFetch: typeof fetch = (input, init = {}) =>
    fetch(input, {
      ...init,
      headers: { ...(init.headers as Record<string, string> ?? {}), cookie },
    });

  try {
    const profile = await apiFetch<Profile>(authedFetch, `/users/${params.id}`);
    const res     = await apiFetch<PostListResponse>(fetch, `/posts?author_id=${params.id}&limit=20`);
    // Hydrate the viewer's like/save state so already-liked posts render red on
    // load (the batch endpoint rejects an empty list, so guard on length).
    const postIds = res.items.map((p) => p.id);
    const me = postIds.length
      ? await getMyInteractionsBatch(authedFetch, postIds).catch(() => ({ items: {} }))
      : { items: {} };
    return { profile, posts: res.items, me: me.items };
  } catch (e) {
    if (e instanceof ApiException && e.status === 404) throw error(404, 'User not found');
    throw e;
  }
};
