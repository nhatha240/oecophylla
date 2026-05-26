import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { error } from '@sveltejs/kit';
import type { Post, Comment, MyInteractions } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  let post: Post;
  try { post = await apiFetch<Post>(fetch, `/posts/${params.id}`); }
  catch (e) { if (e instanceof ApiException && e.status === 404) throw error(404, 'Post not found'); throw e; }
  apiFetch(fetch, `/posts/${params.id}/view`, { method: 'POST' }).catch(() => {});
  let me: MyInteractions | null = null;
  try { me = await apiFetch<MyInteractions>(fetch, `/posts/${params.id}/me`); } catch {}
  const comments = await apiFetch<Comment[]>(fetch, `/posts/${params.id}/comments?limit=20`);
  return { post, me, comments };
};
