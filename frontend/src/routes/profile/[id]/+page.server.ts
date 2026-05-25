import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Profile, Post } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  try {
    const profile = await apiFetch<Profile>(fetch, `/users/${params.id}`);
    const posts   = await apiFetch<Post[]>(fetch, `/posts?author_id=${params.id}&limit=20`);
    return { profile, posts };
  } catch (e) {
    if (e instanceof ApiException && e.status === 404) throw error(404, 'User not found');
    throw e;
  }
};
