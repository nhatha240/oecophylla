import { error, type ServerLoad } from '@sveltejs/kit';
import { ApiException, getAdminReports, getAuditLog } from '$lib/api';

function parseLimit(value: string | null): number {
  const parsed = Number(value ?? '20');
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), 50) : 20;
}

export const load: ServerLoad = async ({ fetch, parent, url }) => {
  const { user } = await parent();
  if (user?.role !== 'admin') throw error(403, 'Forbidden');

  const reportsCursor = url.searchParams.get('reports_cursor') ?? '';
  const auditCursor = url.searchParams.get('audit_cursor') ?? '';
  const actorId = url.searchParams.get('actor_id') ?? '';
  const action = url.searchParams.get('action') ?? '';
  const limit = parseLimit(url.searchParams.get('limit'));

  let reports = { items: [], next_cursor: null } as { items: unknown[]; next_cursor: string | null };
  let audit = { items: [], next_cursor: null } as { items: unknown[]; next_cursor: string | null };
  let reportsError: string | null = null;
  let auditError: string | null = null;

  try {
    reports = await getAdminReports(fetch, { status: 'pending', cursor: reportsCursor || undefined, limit });
  } catch (err) {
    reportsError = err instanceof ApiException ? `${err.status} ${err.code}` : 'Không thể tải danh sách báo cáo.';
  }

  try {
    audit = await getAuditLog(fetch, { cursor: auditCursor || undefined, limit, actor_id: actorId || undefined, action: action || undefined });
  } catch (err) {
    auditError = err instanceof ApiException ? `${err.status} ${err.code}` : 'Không thể tải audit log.';
  }

  return {
    reports,
    reportsError,
    audit,
    auditError,
    filters: { actorId, action, limit }
  };
};
