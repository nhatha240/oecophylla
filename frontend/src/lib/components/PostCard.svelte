<script lang="ts">
  import type { Post } from '$lib/types';
  export let post: Post;
</script>
<article class="glass-surface p-5 mb-3">
  <p class="whitespace-pre-wrap">{post.content}</p>
  <div class="mt-3 flex items-center gap-2 text-mono-meta">
    <span>{new Date(post.created_at).toLocaleString('vi-VN')}</span>
    {#each post.tags as t}<span class="glass-chip">#{t}</span>{/each}
  </div>
</article>
