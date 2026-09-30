import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { apiFetch } from '$lib/api';
import type { PostListResponse } from '$lib/types';

export const load: PageServerLoad = async ({ fetch, parent }) => {
  const { user } = await parent();
  if (!user) throw redirect(303, '/login');
  const posts = await apiFetch<PostListResponse>(fetch, '/posts?author_id=' + encodeURIComponent(user.id) + '&limit=50').then((result) => result.items).catch(() => []);
  return { posts };
};
