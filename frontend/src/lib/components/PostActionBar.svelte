<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import type { Post, MyInteractions } from '$lib/types';
  export let post: Post;
  export let me: MyInteractions | null = null;

  let liked  = me?.liked  ?? false;
  let saved  = me?.saved  ?? false;
  let likeCount = post.like_count;
  let saveCount = post.save_count;

  async function toggle(kind: 'like' | 'save') {
    const wasOn = kind === 'like' ? liked : saved;
    const counter = kind === 'like' ? likeCount : saveCount;
    // optimistic
    if (kind === 'like') { liked = !wasOn;  likeCount = counter + (wasOn ? -1 : 1); }
    else                 { saved = !wasOn;  saveCount = counter + (wasOn ? -1 : 1); }
    try {
      await apiFetch(fetch, `/posts/${post.id}/${kind}`, { method: wasOn ? 'DELETE' : 'POST' });
    } catch (e) {
      // rollback
      if (kind === 'like') { liked = wasOn; likeCount = counter; }
      else                 { saved = wasOn; saveCount = counter; }
      if (e instanceof ApiException && e.status === 401) alert('Vui lòng đăng nhập');
      else alert('Có lỗi xảy ra');
    }
  }
</script>

<div class="mt-3 flex items-center gap-2 text-mono-meta">
  <button class="glass-chip" on:click={() => toggle('like')} aria-pressed={liked}>
    {liked ? '♥' : '♡'} {likeCount}
  </button>
  <button class="glass-chip" on:click={() => toggle('save')} aria-pressed={saved}>
    {saved ? '★' : '☆'} {saveCount}
  </button>
  <a class="glass-chip" href={`/post/${post.id}`}>💬 {post.comment_count}</a>
  <span class="glass-chip">↗ {post.share_count}</span>
</div>
