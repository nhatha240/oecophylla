import { getPostsByTopic } from '$lib/api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
  const topic = params.topic;
  try {
    const data = await getPostsByTopic(fetch, topic);
    return { topic, posts: data.items, nextCursor: data.next_cursor };
  } catch {
    return { topic, posts: [], nextCursor: null };
  }
};
