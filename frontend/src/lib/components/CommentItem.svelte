<script lang="ts">
  import type { Comment } from '$lib/types';
  import CommentForm from './CommentForm.svelte';
  import { apiFetch } from '$lib/api';
  import { user } from '$lib/stores/auth';
  export let c: Comment;
  export let post_id: string;
  let showReply = false;
  let allReplies: Comment[] = [...(c.replies ?? [])];
  let hasMore = c.has_more_replies ?? false;

  async function loadMore() {
    const next = await apiFetch<Comment[]>(fetch, `/comments/${c.id}/replies?limit=20`);
    allReplies = next;
    hasMore = false;
  }
  async function del() {
    if (!confirm('Xóa bình luận này?')) return;
    try {
      await apiFetch(fetch, `/comments/${c.id}`, { method: 'DELETE' });
      c = { ...c, is_deleted: true, content: '[đã xóa]' };
    } catch (e) { alert('Không xóa được'); }
  }
</script>
<li class="glass-surface p-4">
  <div class="text-mono-meta">@{c.author_username} · {new Date(c.created_at).toLocaleString('vi-VN')}</div>
  <p class="mt-1 whitespace-pre-wrap">{c.content}</p>
  <div class="mt-2 flex gap-2 text-sm">
    {#if $user && !c.parent_comment_id}<button class="glass-chip" on:click={() => (showReply = !showReply)}>Phản hồi</button>{/if}
    {#if $user && $user.id === c.author_id && !c.is_deleted}<button class="glass-chip" on:click={del}>Xóa</button>{/if}
  </div>
  {#if showReply}
    <div class="mt-2"><CommentForm post_id={post_id} parent_comment_id={c.id} /></div>
  {/if}
  {#if allReplies.length > 0}
    <ul class="mt-3 ml-6 space-y-2">
      {#each allReplies as r (r.id)}
        <li class="glass-surface p-3">
          <div class="text-mono-meta">@{r.author_username} · {new Date(r.created_at).toLocaleString('vi-VN')}</div>
          <p class="mt-1 whitespace-pre-wrap">{r.content}</p>
        </li>
      {/each}
    </ul>
    {#if hasMore}<button class="glass-chip mt-2 ml-6" on:click={loadMore}>Xem thêm phản hồi…</button>{/if}
  {/if}
</li>
