import type { LayoutServerLoad } from './$types';
import { apiFetch } from '$lib/api';
import type { User } from '$lib/types';

export const load: LayoutServerLoad = async ({ fetch }) => {
  try {
    const body = await apiFetch<{ user: User }>(fetch, '/auth/me');
    return { user: body.user };
  } catch {
    return { user: null };
  }
};
