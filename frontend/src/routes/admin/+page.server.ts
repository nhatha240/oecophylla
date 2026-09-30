import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getAdminMetrics, getAdminReports } from '$lib/api';

export const load: PageServerLoad = async ({ fetch, parent }) => {
  const { user } = await parent();
  if (user?.role !== 'admin') throw redirect(303, '/');
  const [metrics, reports] = await Promise.all([
    getAdminMetrics(fetch).catch(() => null),
    getAdminReports(fetch, { status: 'pending', limit: 10 }).catch(() => ({ items: [], next_cursor: null }))
  ]);
  return { metrics, reports: reports.items };
};
