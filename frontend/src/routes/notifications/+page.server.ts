import type { PageServerLoad } from './$types';
import { listNotifications } from '$lib/api/notifications';

export const load: PageServerLoad = async ({ fetch }) => {
  const notifications = await listNotifications(fetch).catch(() => ({ items: [], next_cursor: null }));
  return { notifications };
};
