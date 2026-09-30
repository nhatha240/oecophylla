import { describe, expect, it, vi } from 'vitest';

class RedirectResponse extends Error {
	constructor(
		public status: number,
		public location: string
	) {
		super(`redirect ${status} ${location}`);
	}
}

vi.mock('@sveltejs/kit', () => ({
	fail: (status: number, data: Record<string, unknown>) => ({ status, ...data }),
	redirect: (status: number, location: string) => {
		throw new RedirectResponse(status, location);
	}
}));

import { actions } from './+page.server';

function loginRequest(emailOrUsername = 'lan@example.com', password = 'Password!123'): Request {
	return new Request('http://localhost/login', {
		method: 'POST',
		headers: { 'content-type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({ email_or_username: emailOrUsername, password })
	});
}

describe('POST /login', () => {
	it('forwards credentials, keeps both session cookies, and redirects after a successful login', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			headers: {
				getSetCookie: () => [
					'oec_access=access-token; Path=/; Max-Age=900; HttpOnly; SameSite=Lax',
					'oec_refresh=refresh-token; Path=/api/v1/auth; Max-Age=604800; HttpOnly; SameSite=Strict'
				]
			}
		});
		const cookies = { set: vi.fn(), delete: vi.fn() };

		await expect(actions.default({ request: loginRequest(), fetch: fetchMock, cookies } as never)).rejects.toMatchObject({
			status: 303,
			location: '/'
		});

		expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', {
			method: 'POST',
			credentials: 'include',
			headers: {
				'content-type': 'application/json',
				'x-requested-with': 'oec-web'
			},
			body: JSON.stringify({ email_or_username: 'lan@example.com', password: 'Password!123' })
		});
		expect(cookies.set).toHaveBeenNthCalledWith(1, 'oec_access', 'access-token', {
			path: '/', maxAge: 900, httpOnly: true, sameSite: 'lax', secure: false
		});
		expect(cookies.set).toHaveBeenNthCalledWith(2, 'oec_refresh', 'refresh-token', {
			path: '/api/v1/auth', maxAge: 604800, httpOnly: true, sameSite: 'strict', secure: false
		});
	});

	it('returns a generic error for invalid credentials without echoing the password', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: false,
			status: 401,
			headers: { getSetCookie: () => [] },
			json: vi.fn().mockResolvedValue({ error: { code: 'UNAUTHORIZED' } })
		});
		const result = await actions.default({
			request: loginRequest('lan@example.com', 'incorrect'),
			fetch: fetchMock,
			cookies: { set: vi.fn(), delete: vi.fn() }
		} as never);

		expect(result).toEqual({ status: 401, error: 'Sai thông tin đăng nhập', email_or_username: 'lan@example.com' });
		expect(result).not.toHaveProperty('password');
	});

	it('preserves leading and trailing spaces in the password', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ ok: true, headers: new Headers() });
		await expect(actions.default({
			request: loginRequest('lan@example.com', '  Password!123  '),
			fetch: fetchMock,
			cookies: { set: vi.fn(), delete: vi.fn() }
		} as never)).rejects.toMatchObject({ status: 303 });
		expect(JSON.parse(fetchMock.mock.calls[0][1].body).password).toBe('  Password!123  ');
	});

	it('rejects blank or oversized credentials before calling the auth service', async () => {
		const fetchMock = vi.fn();
		const result = await actions.default({
			request: loginRequest('', 'x'.repeat(257)),
			fetch: fetchMock,
			cookies: { set: vi.fn(), delete: vi.fn() }
		} as never);

		expect(result).toEqual({
			status: 400,
			error: 'Nhập email hoặc tên người dùng và mật khẩu',
			email_or_username: ''
		});
		expect(fetchMock).not.toHaveBeenCalled();
	});
});
