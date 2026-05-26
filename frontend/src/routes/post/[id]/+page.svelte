<script lang="ts">
  import PostCard from '$lib/components/PostCard.svelte';
  import CommentItem from '$lib/components/CommentItem.svelte';
  import CommentForm from '$lib/components/CommentForm.svelte';
  import ReportDialog from '$lib/components/ReportDialog.svelte';
  import { user } from '$lib/stores/auth';
  export let data: { post: import('$lib/types').Post; me: import('$lib/types').MyInteractions | null; comments: import('$lib/types').Comment[] };
  let showReport = false;
</script>

<PostCard post={data.post} me={data.me} />
{#if $user}
  <div class="mt-3"><button class="glass-chip" on:click={() => (showReport = true)}>Báo cáo</button></div>
{/if}
{#if showReport}
  <ReportDialog post_id={data.post.id} on:close={() => (showReport = false)} />
{/if}

<section class="mt-6">
  <h2 class="text-display-serif text-xl mb-3">Bình luận ({data.post.comment_count})</h2>
  {#if $user}
    <CommentForm post_id={data.post.id} />
  {/if}
  <ul class="mt-4 space-y-3">
    {#each data.comments as c (c.id)}
      <CommentItem {c} post_id={data.post.id} />
    {/each}
    {#if data.comments.length === 0}<p class="text-ink-500">Chưa có bình luận.</p>{/if}
  </ul>
</section>
