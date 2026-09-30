import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { PostListResponse, Profile } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  let profile: Profile;
  try { profile = await apiFetch<Profile>(fetch, '/users/' + params.id); }
  catch (e) { if (e instanceof ApiException && e.status === 404) throw error(404, 'Không tìm thấy hồ sơ'); throw e; }
  const posts = await apiFetch<PostListResponse>(fetch, '/posts?author_id=' + encodeURIComponent(params.id) + '&limit=20').then((res) => res.items).catch(() => []);
  return { profile, posts };
};
