<script lang="ts">
  import type { Post, MyInteractions } from '$lib/types';
  import PostActionBar from './PostActionBar.svelte';
  export let post: Post;
  export let me: MyInteractions | null = null;
</script>
<article class="glass-surface p-5 mb-3">
  <p class="whitespace-pre-wrap">{post.content}</p>
  <div class="mt-3 flex items-center gap-2 text-mono-meta">
    <span>{new Date(post.created_at).toLocaleString('vi-VN')}</span>
    {#each post.tags as t}<span class="glass-chip">#{t}</span>{/each}
  </div>
  <PostActionBar {post} {me} />
</article>
