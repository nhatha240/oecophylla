import { describe, expect, it, vi } from 'vitest';
import { createComment, deleteComment, reportPost } from './discussion';

function fetcher(status = 201) {
  return vi.fn().mockResolvedValue(new Response(status === 201 ? JSON.stringify({ id: 'created-1', parent_comment_id: 'comment-1' }) : null, { status })) as unknown as typeof fetch;
}

describe('discussion mutations', () => {
  it('sends a reply with its parent id', async () => {
    const fetch = fetcher();
    await expect(createComment(fetch, 'post-1', 'Trả lời @minh', 'comment-1')).resolves.toEqual({ id: 'created-1', parent_comment_id: 'comment-1' });
    expect(fetch).toHaveBeenCalledWith('/api/v1/posts/post-1/comments', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ content: 'Trả lời @minh', parent_comment_id: 'comment-1' })
    }));
  });

  it('deletes a comment through the author endpoint', async () => {
    const fetch = fetcher(204);
    await deleteComment(fetch, 'comment-1');
    expect(fetch).toHaveBeenCalledWith('/api/v1/comments/comment-1', expect.objectContaining({ method: 'DELETE' }));
  });

  it('sends a report reason and detail', async () => {
    const fetch = fetcher();
    await reportPost(fetch, 'post-1', 'spam', 'Quảng cáo lặp lại');
    expect(fetch).toHaveBeenCalledWith('/api/v1/posts/post-1/report', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ reason: 'spam', detail: 'Quảng cáo lặp lại' })
    }));
  });
});
