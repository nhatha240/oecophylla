import { describe, expect, it, vi } from 'vitest';

class RedirectResponse extends Error {
  constructor(public status: number, public location: string) { super('redirect'); }
}

vi.mock('@sveltejs/kit', async () => {
  const actual = await vi.importActual<typeof import('@sveltejs/kit')>('@sveltejs/kit');
  return { ...actual, redirect: (status: number, location: string) => { throw new RedirectResponse(status, location); } };
});
vi.mock('$lib/api', () => ({ getAdminMetrics: vi.fn(), getAdminReports: vi.fn() }));

import { getAdminMetrics, getAdminReports } from '$lib/api';
import { load } from './+page.server';

describe('admin page access', () => {
  it.each([null, { id: 'u1', role: 'user' }])('redirects a non-admin without requesting admin data', async (user) => {
    await expect(load({ parent: async () => ({ user }), fetch: vi.fn() } as never))
      .rejects.toMatchObject({ status: 303, location: '/' });
    expect(getAdminMetrics).not.toHaveBeenCalled();
    expect(getAdminReports).not.toHaveBeenCalled();
  });

  it('loads admin data for an admin', async () => {
    vi.mocked(getAdminMetrics).mockResolvedValueOnce({ total_posts: 5 } as never);
    vi.mocked(getAdminReports).mockResolvedValueOnce({ items: [], next_cursor: null });
    await expect(load({ parent: async () => ({ user: { id: 'a1', role: 'admin' } }), fetch: vi.fn() } as never))
      .resolves.toMatchObject({ metrics: { total_posts: 5 }, reports: [] });
  });
});
