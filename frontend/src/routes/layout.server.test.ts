import { describe, expect, it, vi } from 'vitest';

class RedirectResponse extends Error {
	constructor(
		public status: number,
		public location: string
	) {
		super(`redirect ${status} ${location}`);
	}
}

vi.mock('@sveltejs/kit', async () => {
	const actual = await vi.importActual<typeof import('@sveltejs/kit')>('@sveltejs/kit');
	return {
		...actual,
		redirect: (status: number, location: string) => {
			throw new RedirectResponse(status, location);
		}
	};
});

import { load } from './+layout.server';

function loadRoute(pathname: string, fetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 })), refresh?: string) {
	return load({
		fetch,
		url: new URL(`http://localhost${pathname}`),
		cookies: { get: vi.fn().mockReturnValue(refresh), set: vi.fn(), delete: vi.fn() }
	} as never);
}

describe('root layout authentication guard', () => {
	it('redirects an unauthenticated request to login on protected routes', async () => {
		await expect(loadRoute('/')).rejects.toMatchObject({ status: 303, location: '/login' });
	});

	it('lets an unauthenticated visitor reach the login route', async () => {
		await expect(loadRoute('/login')).resolves.toEqual({ user: null, learnedPrefs: null });
	});

	it('refreshes an expired access token and loads the current user', async () => {
		const fetch = vi.fn()
			.mockResolvedValueOnce(new Response(null, { status: 401 }))
			.mockResolvedValueOnce(new Response('{}', { headers: { 'set-cookie': 'oec_access=new-token; Path=/; HttpOnly; SameSite=Lax' } }))
			.mockResolvedValueOnce(Response.json({ user: { id: 'admin-1', role: 'admin' } }));
		await expect(loadRoute('/admin', fetch, 'refresh-token')).resolves.toEqual({ user: { id: 'admin-1', role: 'admin' }, learnedPrefs: null });
		expect(fetch).toHaveBeenNthCalledWith(3, '/api/v1/auth/me', { headers: { cookie: 'oec_access=new-token' } });
	});

	it('loads action-derived topic weights for the authenticated user', async () => {
		const fetch = vi.fn()
			.mockResolvedValueOnce(Response.json({ user: { id: 'reader-1', topic_prefs: ['tech'] } }))
			.mockResolvedValueOnce(Response.json({ user_id: 'reader-1', topic_weights: { science: 2 }, updated_at: '2026-10-08T00:00:00Z' }));
		await expect(loadRoute('/', fetch)).resolves.toMatchObject({
			user: { topic_prefs: ['tech'] }, learnedPrefs: { topic_weights: { science: 2 } }
		});
		expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/users/reader-1/preferences', expect.anything());
	});
});
