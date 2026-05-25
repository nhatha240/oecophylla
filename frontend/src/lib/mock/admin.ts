export const mockReports = [
  { id: 'r1', post_id: 'p1', reason: 'spam', status: 'pending', created_at: new Date().toISOString() },
  { id: 'r2', post_id: 'p2', reason: 'misinformation', status: 'pending', created_at: new Date().toISOString() },
];
export const mockMetrics = { users: 50, posts: 100, reports_pending: 2, ctr: 0.14 };
