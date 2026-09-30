import { fail, redirect, type Actions } from '@sveltejs/kit';
import { applyResponseCookies } from '$lib/server/sessionCookies';

export const actions: Actions = {
  default: async ({ request, fetch, cookies }) => {
    const form = await request.formData();
    const username = String(form.get('username') ?? '').trim();
    const email = String(form.get('email') ?? '').trim();
    const display_name = String(form.get('display_name') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if (!/^[a-z0-9_]{3,30}$/.test(username) || !email.includes('@') || password.length < 8 || password.length > 128) {
      return fail(400, { error: 'Vui lòng kiểm tra tên người dùng, email và mật khẩu.' });
    }
    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST', credentials: 'include',
        headers: { 'content-type': 'application/json', 'x-requested-with': 'oec-web' },
        body: JSON.stringify({ username, email, display_name: display_name || null, password })
      });
      if (response.status === 409) return fail(409, { error: 'Tên người dùng hoặc email đã tồn tại.' });
      if (!response.ok) return fail(response.status >= 500 ? 500 : 400, { error: 'Không thể đăng ký với thông tin này.' });
      applyResponseCookies(cookies, response);
    } catch { return fail(500, { error: 'Không thể kết nối. Vui lòng thử lại.' }); }
    throw redirect(303, '/');
  }
};
