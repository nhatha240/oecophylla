import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import { applyResponseCookies, getResponseCookieValue } from '$lib/server/sessionCookies';
import type { User } from '$lib/types';
import { getUserPreferences } from '$lib/api';

export const load: LayoutServerLoad = async ({ fetch, url, cookies }) => {
  try {
    let response = await fetch('/api/v1/auth/me');
    if (response.status === 401 && cookies.get('oec_refresh')) {
      const refreshed = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'x-requested-with': 'oec-web' }
      });
      if (refreshed.ok) {
        applyResponseCookies(cookies, refreshed);
        const access = getResponseCookieValue(refreshed, 'oec_access');
        if (access) {
          response = await fetch('/api/v1/auth/me', {
            headers: { cookie: `oec_access=${access}` }
          });
        }
      }
    }
    if (!response.ok) throw new Error('Unauthenticated');
    const body = await response.json() as { user: User };
    const learnedPrefs = await getUserPreferences(fetch, body.user.id);
    return { user: body.user, learnedPrefs };
  } catch {
    if (url.pathname !== '/login' && url.pathname !== '/register') {
      throw redirect(303, '/login');
    }
    return { user: null, learnedPrefs: null };
  }
};
