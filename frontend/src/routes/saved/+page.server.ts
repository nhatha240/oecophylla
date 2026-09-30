import type { PageServerLoad } from './$types';
import { getSavedPosts } from '$lib/api';

export const load: PageServerLoad = async ({ fetch }) => {
  const saved = await getSavedPosts(fetch).catch(() => ({ items: [], next_cursor: null }));
  return { saved };
};
