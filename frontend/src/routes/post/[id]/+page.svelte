<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import CommentItem from '$lib/components/CommentItem.svelte';
  import CommentForm from '$lib/components/CommentForm.svelte';
  import ReportDialog from '$lib/components/ReportDialog.svelte';
  import { user } from '$lib/stores/auth';
  export let data: { post: import('$lib/types').Post; me: import('$lib/types').MyInteractions | null; comments: import('$lib/types').Comment[] };
  let showReport = false;
</script>

<div class="reader">
  <div class="crumbs">
    <a href="/" style="color: var(--muted);"><Icon name="ArrowLeft" size={12} style="vertical-align: -2px" /> Quay lại bảng tin</a>
  </div>

  <div style="display: flex; gap: 8px; margin-bottom: 16px; align-items: center; flex-wrap: wrap;">
    <span class="chip active">Bài viết</span>
    <span class="t-meta"><Icon name="Clock" size={12} style="vertical-align: -2px" /> {new Date(data.post.created_at).toLocaleString('vi-VN')}</span>
  </div>

  <h1>{data.post.content.length > 140 ? `${data.post.content.slice(0, 140)}…` : data.post.content}</h1>
  <p class="dek">{data.post.content}</p>

  <div class="why-card">
    <h4><Icon name="Sparkle" size={14} /> Vì sao bạn thấy bài viết này?</h4>
    <p>Bài viết đang có tương tác trong mạng lưới của bạn và được phân phối qua feed hiện tại của Oecophylla.</p>
    <div class="why-tags">
      {#each data.post.tags as tag}
        <span class="chip outline">#{tag}</span>
      {/each}
    </div>
  </div>

  <div class="reader-actions">
    <a class="post-action" href="#comments"><Icon name="Comment" size={16} /> {data.post.comment_count} bình luận</a>
    <span class="post-action"><Icon name="Eye" size={16} /> {data.post.view_count} lượt xem</span>
    <span class="post-action"><Icon name="Share" size={16} /> {data.post.share_count} chia sẻ</span>
    {#if $user}
      <button class="post-action" on:click={() => (showReport = true)}><Icon name="Flag" size={16} /> Báo cáo</button>
    {/if}
  </div>

  <section id="comments">
    <h2 class="serif" style="font-size: 26px; margin: 0 0 16px;">Bình luận ({data.post.comment_count})</h2>
    {#if $user}
      <CommentForm post_id={data.post.id} />
    {/if}
    <ul style="margin-top: 16px; padding: 0; list-style: none;">
      {#each data.comments as c (c.id)}
        <CommentItem {c} post_id={data.post.id} />
      {/each}
      {#if data.comments.length === 0}<p class="muted">Chưa có bình luận.</p>{/if}
    </ul>
  </section>
</div>

{#if showReport}
  <ReportDialog post_id={data.post.id} on:close={() => (showReport = false)} />
{/if}
