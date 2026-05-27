import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { ApiException } from '$lib/api';
import { applyResponseCookies } from '$lib/server/cookies';

export const actions: Actions = {
  default: async ({ request, fetch, cookies }) => {
    const data = await request.formData();
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'content-type': 'application/json',
          'x-requested-with': 'oec-web',
        },
        body: JSON.stringify({
          email_or_username: String(data.get('email_or_username') ?? ''),
          password: String(data.get('password') ?? ''),
        }),
      });
      applyResponseCookies(cookies, response);
      if (!response.ok) {
        let body: { error?: { code?: string; details?: unknown } } | null = null;
        try { body = await response.json(); } catch { /* ignore parse errors */ }
        throw new ApiException(response.status, body?.error?.code ?? 'UNKNOWN', body?.error?.details);
      }
    } catch (e) {
      if (e instanceof ApiException && e.status === 401) return fail(401, { error: 'Sai thông tin đăng nhập' });
      console.error('[login action error]', {
        email_or_username: String(data.get('email_or_username') ?? ''),
        password: String(data.get('password') ?? ''),
        error: e,
      });
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
