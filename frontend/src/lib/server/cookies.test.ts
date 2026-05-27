import { describe, expect, it, vi } from 'vitest';

import { applyResponseCookies } from './cookies';

function makeCookies() {
  return {
    set: vi.fn(),
    delete: vi.fn(),
  };
}

describe('applyResponseCookies', () => {
  it('forwards multiple set-cookie headers to svelte cookies', () => {
    const cookies = makeCookies();
    const response = {
      headers: {
        getSetCookie: () => [
          'oec_access=access-token; Path=/; Max-Age=900; HttpOnly; SameSite=Lax',
          'oec_refresh=refresh-token; Path=/api/v1/auth; Max-Age=604800; HttpOnly; SameSite=Strict',
        ],
      },
    };

    applyResponseCookies(cookies as any, response as any);

    expect(cookies.set).toHaveBeenCalledTimes(2);
    expect(cookies.set).toHaveBeenNthCalledWith(1, 'oec_access', 'access-token', {
      path: '/',
      maxAge: 900,
      httpOnly: true,
      sameSite: 'lax',
      secure: false,
    });
    expect(cookies.set).toHaveBeenNthCalledWith(2, 'oec_refresh', 'refresh-token', {
      path: '/api/v1/auth',
      maxAge: 604800,
      httpOnly: true,
      sameSite: 'strict',
      secure: false,
    });
  });

  it('deletes cookies when upstream clears them', () => {
    const cookies = makeCookies();
    const response = {
      headers: {
        getSetCookie: () => ['oec_access=; Path=/; Max-Age=0; HttpOnly'],
      },
    };

    applyResponseCookies(cookies as any, response as any);

    expect(cookies.delete).toHaveBeenCalledWith('oec_access', {
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'lax',
    });
  });
});
