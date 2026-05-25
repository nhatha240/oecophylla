import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Post } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  try {
    const post = await apiFetch<Post>(fetch, `/posts/${params.id}`);
    await apiFetch(fetch, `/posts/${params.id}/view`, { method: 'POST' }).catch(() => {});
    return { post };
  } catch (e) {
    if (e instanceof ApiException && e.status === 404) throw error(404, 'Post not found');
    throw e;
  }
};
