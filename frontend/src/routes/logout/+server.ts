import type { RequestHandler } from './$types';
import { redirect } from '@sveltejs/kit';
import { apiFetch } from '$lib/api';

export const POST: RequestHandler = async ({ fetch }) => {
  try { await apiFetch(fetch, '/auth/logout', { method: 'DELETE' }); } catch {}
  throw redirect(303, '/login');
};
