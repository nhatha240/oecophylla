import type { RequestHandler } from './$types';
import { redirect } from '@sveltejs/kit';
import { applyResponseCookies } from '$lib/server/cookies';

export const POST: RequestHandler = async ({ fetch, cookies }) => {
  try {
    const response = await fetch('/api/v1/auth/logout', {
      method: 'DELETE',
      credentials: 'include',
      headers: {
        'x-requested-with': 'oec-web',
      },
    });
    applyResponseCookies(cookies, response);
  } catch {}
  throw redirect(303, '/login');
};
