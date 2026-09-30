import type { RequestHandler } from './$types';
import { redirect } from '@sveltejs/kit';
import { applyResponseCookies } from '$lib/server/sessionCookies';

export const POST: RequestHandler = async ({ fetch, cookies }) => {
  try {
    const response = await fetch('/api/v1/auth/logout', {
      method: 'DELETE', credentials: 'include', headers: { 'x-requested-with': 'oec-web' }
    });
    if (response.ok) applyResponseCookies(cookies, response);
  } catch { /* Redirect to login even when the upstream is unavailable. */ }
  cookies.delete('oec_access', { path: '/' });
  cookies.delete('oec_refresh', { path: '/api/v1/auth' });
  throw redirect(303, '/login');
};
