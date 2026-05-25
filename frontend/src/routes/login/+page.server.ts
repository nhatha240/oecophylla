import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const data = await request.formData();
    try {
      await apiFetch(fetch, '/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email_or_username: String(data.get('email_or_username') ?? ''),
          password: String(data.get('password') ?? ''),
        }),
      });
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) return fail(401, { error: 'Sai thông tin đăng nhập' });
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
