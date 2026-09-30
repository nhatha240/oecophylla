import { fail, redirect, type Actions } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';
import type { Post } from '$lib/types';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const form = await request.formData();
    const content = String(form.get('content') ?? '').trim();
    const tags = String(form.get('tags') ?? '').split(',').map((tag) => tag.trim()).filter(Boolean);
    const mediaUrl = String(form.get('media_url') ?? '').trim();
    if (!content) return fail(400, { error: 'Vui lòng nhập nội dung bài viết.', content });
    let post: Post;
    try {
      post = await apiFetch<Post>(fetch, '/posts', { method: 'POST', body: JSON.stringify({ content, tags, media_urls: mediaUrl ? [mediaUrl] : [] }) });
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) throw redirect(303, '/login');
      return fail(400, { error: 'Không thể đăng bài. Hãy kiểm tra nội dung và thử lại.', content });
    }
    throw redirect(303, '/post/' + post.id);
  }
};
