<script lang="ts">
  import type { Comment } from '$lib/types';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
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

<li class="comment">
  <div class="avatar s40">{(c.author_display_name ?? c.author_username).slice(0, 1).toUpperCase()}</div>
  <div style="flex: 1;">
    <div class="c-meta">
      <span class="name">{c.author_display_name ?? c.author_username}</span>
      <span class="time">@{c.author_username} · {new Date(c.created_at).toLocaleString('vi-VN')}</span>
    </div>
    <p class="c-body whitespace-pre-wrap">{c.content}</p>
    <div class="c-acts">
      {#if $user && !c.parent_comment_id}<button on:click={() => (showReply = !showReply)}><Icon name="ArrowRight" size={13} /> Phản hồi</button>{/if}
      {#if $user && $user.id === c.author_id && !c.is_deleted}<button on:click={del}><Icon name="X" size={13} /> Xóa</button>{/if}
    </div>

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
            <div>
              <div class="c-meta">
                <span class="name">{r.author_display_name ?? r.author_username}</span>
                <span class="time">@{r.author_username} · {new Date(r.created_at).toLocaleString('vi-VN')}</span>
              </div>
              <p class="c-body whitespace-pre-wrap">{r.content}</p>
            </div>
          </li>
        {/each}
      </ul>
      {#if hasMore}<button class="btn ghost sm" style="margin-top: 8px;" on:click={loadMore}>Xem thêm phản hồi…</button>{/if}
    {/if}
  </div>
</li>
