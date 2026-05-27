import { error, type ServerLoad } from '@sveltejs/kit';
import { apiFetch, ApiException } from '$lib/api';
import type { AdminAuditLog, AdminReport, CursorPage } from '$lib/types';

function parseLimit(value: string | null): number {
  const parsed = Number(value ?? '20');
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), 50) : 20;
}

async function safeCursorPage<T>(
  fetchImpl: typeof fetch,
  path: string
): Promise<{ page: CursorPage<T>; available: boolean }> {
  try {
    const page = await apiFetch<CursorPage<T>>(fetchImpl, path);
    return { page, available: true };
  } catch (err) {
    if (err instanceof ApiException && [404, 500, 502, 503].includes(err.status)) {
      return { page: { items: [], next_cursor: null }, available: false };
    }
    throw err;
  }
}

export const load: ServerLoad = async ({ fetch, parent, url }) => {
  const { user } = await parent();
  if (user?.role !== 'admin') throw error(403, 'Forbidden');

  const reportsCursor = url.searchParams.get('reports_cursor') ?? '';
  const auditCursor = url.searchParams.get('audit_cursor') ?? '';
  const actorId = url.searchParams.get('actor_id') ?? '';
  const action = url.searchParams.get('action') ?? '';
  const limit = parseLimit(url.searchParams.get('limit'));

  const reportsQuery = new URLSearchParams({ status: 'pending', limit: String(limit) });
  if (reportsCursor) reportsQuery.set('cursor', reportsCursor);

  const auditQuery = new URLSearchParams({ limit: String(limit) });
  if (auditCursor) auditQuery.set('cursor', auditCursor);
  if (actorId) auditQuery.set('actor_id', actorId);
  if (action) auditQuery.set('action', action);

  const [reports, audit] = await Promise.all([
    safeCursorPage<AdminReport>(fetch, `/admin/reports?${reportsQuery.toString()}`),
    safeCursorPage<AdminAuditLog>(fetch, `/admin/audit-logs?${auditQuery.toString()}`)
  ]);

  return {
    reports: reports.page,
    reportsAvailable: reports.available,
    audit: audit.page,
    auditAvailable: audit.available,
    filters: {
      actorId,
      action,
      limit
    }
  };
};
