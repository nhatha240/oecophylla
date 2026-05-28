<script lang="ts">
  import type { Comment } from '$lib/types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import CommentForm from './CommentForm.svelte';
  import { apiFetch } from '$lib/api';
  import { user } from '$lib/stores/auth';
  import { showToast } from '$lib/stores/toast';

  export let c: Comment;
  export let post_id: string;

  let showReply = false;
  let replyingTo: string | null = null;
  let showDeleteConfirm = false;
  let allReplies: Comment[] = [...(c.replies ?? [])];
  let hasMore = c.has_more_replies ?? false;

  async function loadMore() {
    const next = await apiFetch<Comment[]>(fetch, `/comments/${c.id}/replies?limit=20`);
    allReplies = next;
    hasMore = false;
  }

  async function del() {
    try {
      await apiFetch(fetch, `/comments/${c.id}`, { method: 'DELETE' });
      c = { ...c, is_deleted: true, content: '[đã xóa]' };
      showDeleteConfirm = false;
      showToast('Đã xóa bình luận.');
    } catch {
      showToast('Không xóa được bình luận.');
    }
  }

  function handleReplySubmit(reply: Comment) {
    allReplies = [...allReplies, reply];
    replyingTo = null;
  }
</script>

<li class="comment">
  <div class="avatar s40">{(c.author_display_name ?? c.author_username).slice(0, 1).toUpperCase()}</div>
  <div style="flex: 1;">
    <div class="c-meta">
      <span class="name">{c.author_display_name ?? c.author_username}</span>
      <span class="time">@{c.author_username} · {new Date(c.created_at).toLocaleString('vi-VN')}</span>
    </div>
    <p class="c-body whitespace-pre-wrap">{c.content}</p>
    <div class="c-acts">
      {#if $user && !c.parent_comment_id}<button type="button" on:click={() => { showReply = !showReply; replyingTo = null; }}><Icon name="ArrowRight" size={13} /> Phản hồi</button>{/if}
      {#if $user && $user.id === c.author_id && !c.is_deleted}
        <button type="button" on:click={() => (showDeleteConfirm = !showDeleteConfirm)}><Icon name="X" size={13} /> Xóa</button>
      {/if}
    </div>

    {#if showDeleteConfirm}
      <div class="glass-surface mt-3 flex items-center justify-between gap-3 rounded-[20px] px-4 py-3 text-sm text-slate-600">
        <span>Xóa bình luận này?</span>
        <span class="flex gap-2">
          <button class="glass-chip" type="button" on:click={() => (showDeleteConfirm = false)}>Giữ lại</button>
          <button class="glass-button-primary" type="button" on:click={del}>Xóa</button>
        </span>
      </div>
    {/if}

    {#if showReply}
      <div class="replies" style="margin-top: 12px;">
        <CommentForm post_id={post_id} parent_comment_id={c.id} />
      </div>
    {/if}

    {#if allReplies.length > 0}
      <ul class="replies">
        {#each allReplies as r (r.id)}
          <li class="comment reply">
            <div class="avatar s32">{(r.author_display_name ?? r.author_username).slice(0, 1).toUpperCase()}</div>
            <div style="flex: 1; min-width: 0;">
              <div class="c-meta">
                <span class="name">{r.author_display_name ?? r.author_username}</span>
                <span class="time">@{r.author_username} · {new Date(r.created_at).toLocaleString('vi-VN')}</span>
              </div>
              <p class="c-body whitespace-pre-wrap">{r.content}</p>
              <div class="c-acts">
                {#if $user}
                  <button type="button" on:click={() => (replyingTo = replyingTo === r.id ? null : r.id)}>
                    <Icon name="ArrowRight" size={13} /> Trả lời
                  </button>
                {/if}
              </div>
              {#if replyingTo === r.id}
                <div style="margin-top: 8px;">
                  <CommentForm
                    {post_id}
                    parent_comment_id={r.id}
                    on:submitted={(e) => handleReplySubmit(e.detail)}
                  />
                </div>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
      {#if hasMore}<button class="btn ghost sm" type="button" style="margin-top: 8px;" on:click={loadMore}>Xem thêm phản hồi…</button>{/if}
    {/if}
  </div>
</li>
