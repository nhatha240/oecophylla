import { getPostsByTag } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const tag = params.tag;
  try {
    const data = await getPostsByTag(fetch, tag);
    return { tag, posts: data.items, nextCursor: data.next_cursor };
  } catch {
    return { tag, posts: [], nextCursor: null };
  }
};
