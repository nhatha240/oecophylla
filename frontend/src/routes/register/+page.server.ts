import type { Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';
import { ApiException } from '$lib/api';
import { applyResponseCookies } from '$lib/server/cookies';

export const actions: Actions = {
  default: async ({ request, fetch, cookies }) => {
    const f = await request.formData();
    const payload = {
      username: String(f.get('username') ?? ''),
      email: String(f.get('email') ?? ''),
      password: String(f.get('password') ?? ''),
      display_name: (f.get('display_name') as string) || null,
    };

    console.log('[register action request]', {
      username: payload.username,
      email: payload.email,
      displayName: payload.display_name,
      passwordLength: payload.password.length,
      target: '/api/v1/auth/register',
    });

    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'content-type': 'application/json',
          'x-requested-with': 'oec-web',
        },
        body: JSON.stringify(payload),
      });
      applyResponseCookies(cookies, response);
      if (!response.ok) {
        let body: { error?: { code?: string; details?: unknown } } | null = null;
        try { body = await response.json(); } catch { /* ignore parse errors */ }
        throw new ApiException(response.status, body?.error?.code ?? 'UNKNOWN', body?.error?.details);
      }
      console.log('[register action success]', {
        username: payload.username,
        email: payload.email,
      });
    } catch (e) {
      console.error('[register action error]', {
        username: payload.username,
        email: payload.email,
        error: e,
      });
      if (e instanceof ApiException) {
        if (e.status === 409) return fail(409, { error: 'Username hoặc email đã tồn tại' });
        if (e.status === 400) return fail(400, { error: 'Thông tin không hợp lệ' });
      }
      return fail(500, { error: 'Lỗi máy chủ' });
    }
    throw redirect(303, '/');
  },
};
