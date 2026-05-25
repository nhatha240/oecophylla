import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';
import type { Post } from '$lib/types';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const f = await request.formData();
    const tags = String(f.get('tags') ?? '').split(',').map(s => s.trim()).filter(Boolean);
    try {
      const post = await apiFetch<Post>(fetch, '/posts', {
        method: 'POST',
        body: JSON.stringify({ content: String(f.get('content') ?? ''), tags }),
      });
      throw redirect(303, `/post/${post.id}`);
    } catch (e) {
      if (e instanceof ApiException && e.status === 400) return fail(400, { error: 'Nội dung không hợp lệ' });
      if (e instanceof ApiException && e.status === 401) throw redirect(303, '/login');
      throw e;
    }
  },
};
