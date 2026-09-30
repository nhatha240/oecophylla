import { fail, redirect, type Actions } from '@sveltejs/kit';
import { applyResponseCookies } from '$lib/server/sessionCookies';

function getText(form: FormData, name: string): string {
	const value = form.get(name);
	return typeof value === 'string' ? value.trim() : '';
}


export const actions: Actions = {
	default: async ({ request, fetch, cookies }) => {
		const form = await request.formData();
		const emailOrUsername = getText(form, 'email_or_username');
		const passwordValue = form.get('password');
		const password = typeof passwordValue === 'string' ? passwordValue : '';

		if (!emailOrUsername || !password || emailOrUsername.length > 254 || password.length > 256) {
			return fail(400, {
				error: 'Nhập email hoặc tên người dùng và mật khẩu',
				email_or_username: emailOrUsername
			});
		}

		try {
			const response = await fetch('/api/v1/auth/login', {
				method: 'POST',
				credentials: 'include',
				headers: {
					'content-type': 'application/json',
					'x-requested-with': 'oec-web'
				},
				body: JSON.stringify({ email_or_username: emailOrUsername, password })
			});

			if (!response.ok) {
				if (response.status === 401) {
					return fail(401, { error: 'Sai thông tin đăng nhập', email_or_username: emailOrUsername });
				}
				return fail(500, { error: 'Không thể đăng nhập lúc này', email_or_username: emailOrUsername });
			}

			applyResponseCookies(cookies, response);
		} catch {
			return fail(500, { error: 'Không thể đăng nhập lúc này', email_or_username: emailOrUsername });
		}

		throw redirect(303, '/');
	}
};
