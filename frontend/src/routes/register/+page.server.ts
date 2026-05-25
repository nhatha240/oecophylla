import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';

export const actions: Actions = {
  default: async ({ request, fetch }) => {
    const f = await request.formData();
    try {
      await apiFetch(fetch, '/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: String(f.get('username') ?? ''),
          email: String(f.get('email') ?? ''),
          password: String(f.get('password') ?? ''),
          display_name: (f.get('display_name') as string) || null,
        }),
      });
    } catch (e) {
      if (e instanceof ApiException) {
        if (e.status === 409) return fail(409, { error: 'Username hoặc email đã tồn tại' });
        if (e.status === 400) return fail(400, { error: 'Thông tin không hợp lệ' });
      }
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
