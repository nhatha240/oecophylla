import type { PageServerLoad } from './$types';
import { apiFetch, ApiException } from '$lib/api';
import { redirect } from '@sveltejs/kit';
import type { Profile } from '$lib/types';

export const load: PageServerLoad = async ({ fetch, parent }) => {
  const { user } = await parent();
  if (!user) throw redirect(302, '/login');

  try {
    const profile = await apiFetch<Profile>(fetch, `/users/${user.id}`);
    return { profile };
  } catch (e) {
    if (e instanceof ApiException && (e.status === 401 || e.status === 403)) {
      throw redirect(302, '/login');
    }
    throw e;
  }
};
