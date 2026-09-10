import { error, fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { ApiException, apiFetch, updatePost } from '$lib/api';
import type { Post, User } from '$lib/types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const auth = await apiFetch<{ user: User }>(fetch, '/auth/me').catch(() => null);
  if (!auth) throw redirect(303, '/login');

  const post = await apiFetch<Post>(fetch, `/posts/${params.id}`).catch((cause) => {
    if (cause instanceof ApiException && cause.status === 404) throw error(404, 'Post not found');
    throw cause;
  });
  if (post.author_id !== auth.user.id && auth.user.role !== 'admin') {
    throw error(403, 'Bạn không có quyền sửa bài viết này');
  }
  return { post };
};

export const actions: Actions = {
  default: async ({ params, request, fetch }) => {
    const form = await request.formData();
    const tags = String(form.get('tags') ?? '')
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    const media_urls = form.getAll('media_urls[]').map(String).filter(Boolean);
    try {
      await updatePost(fetch, params.id, {
        content: String(form.get('content') ?? ''),
        tags,
        media_urls
      });
    } catch (cause) {
      if (cause instanceof ApiException && cause.status === 400) {
        return fail(400, { error: 'Nội dung cập nhật không hợp lệ' });
      }
      if (cause instanceof ApiException && cause.status === 401) throw redirect(303, '/login');
      if (cause instanceof ApiException && cause.status === 403) {
        return fail(403, { error: 'Bạn không có quyền sửa bài viết này' });
      }
      throw cause;
    }
    throw redirect(303, `/post/${params.id}`);
  }
};
