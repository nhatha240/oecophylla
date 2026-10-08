import { apiFetch, type Fetch } from './api';
import type { ReportReason } from './types';

export interface CommentReceipt { id: string; parent_comment_id: string | null; }

export async function createComment(fetcher: Fetch, postId: string, content: string, parentCommentId: string | null = null): Promise<CommentReceipt> {
  return apiFetch<CommentReceipt>(fetcher, `/posts/${postId}/comments`, {
    method: 'POST',
    body: JSON.stringify({ content: content.trim(), parent_comment_id: parentCommentId })
  });
}

export async function deleteComment(fetcher: Fetch, commentId: string): Promise<void> {
  await apiFetch(fetcher, `/comments/${commentId}`, { method: 'DELETE' });
}

export async function reportPost(fetcher: Fetch, postId: string, reason: ReportReason, detail: string): Promise<void> {
  await apiFetch(fetcher, `/posts/${postId}/report`, {
    method: 'POST',
    body: JSON.stringify({ reason, detail: detail.trim() || null })
  });
}
