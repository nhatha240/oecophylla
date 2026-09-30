import { describe, expect, it, vi } from 'vitest';

class RedirectResponse extends Error {
  constructor(public status: number, public location: string) { super('redirect'); }
}

vi.mock('@sveltejs/kit', () => ({
  fail: (status: number, data: Record<string, unknown>) => ({ status, ...data }),
  redirect: (status: number, location: string) => { throw new RedirectResponse(status, location); }
}));

import { actions } from './+page.server';

function registerRequest(username = 'nguyen_minh'): Request {
  return new Request('http://localhost/register', {
    method: 'POST',
    body: new URLSearchParams({ username, email: 'minh@example.com', display_name: 'Nguyễn Minh', password: 'a-safe-password' })
  });
}

describe('POST /register', () => {
  it('forwards valid details, applies HTTP-only session cookies, then redirects', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'set-cookie': 'oec_access=token; Path=/; Max-Age=900; HttpOnly; SameSite=Lax' })
    });
    const cookies = { set: vi.fn(), delete: vi.fn() };
    await expect(actions.default({ request: registerRequest(), fetch: fetchMock, cookies } as never)).rejects.toMatchObject({ status: 303, location: '/' });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/register', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ username: 'nguyen_minh', email: 'minh@example.com', display_name: 'Nguyễn Minh', password: 'a-safe-password' })
    }));
    expect(cookies.set).toHaveBeenCalledWith('oec_access', 'token', { path: '/', httpOnly: true, sameSite: 'lax', secure: false, maxAge: 900 });
  });

  it('rejects an invalid username before calling the API', async () => {
    const fetchMock = vi.fn();
    const result = await actions.default({ request: registerRequest('Invalid User'), fetch: fetchMock, cookies: { set: vi.fn() } } as never);
    expect(result).toMatchObject({ status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
