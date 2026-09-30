import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Comment, MyInteractions, Post, Profile } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  let post: Post;
  try { post = await apiFetch<Post>(fetch, '/posts/' + params.id); }
  catch (e) { if (e instanceof ApiException && e.status === 404) throw error(404, 'Không tìm thấy bài viết'); throw e; }
  const [me, comments, author] = await Promise.all([
    apiFetch<MyInteractions>(fetch, '/posts/' + params.id + '/me').catch(() => null),
    apiFetch<Comment[]>(fetch, '/posts/' + params.id + '/comments?limit=20').catch(() => []),
    apiFetch<Profile>(fetch, '/users/' + post.author_id).catch(() => null)
  ]);
  return { post, me, comments, author };
};
