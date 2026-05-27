<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
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

<div class="post-actions">
  <button class={`post-action like ${liked ? 'active' : ''}`} on:click={() => toggle('like')} aria-pressed={liked}>
    <Icon name={liked ? 'HeartFill' : 'Heart'} size={16} /> {likeCount}
  </button>
  <button class={`post-action save ${saved ? 'active' : ''}`} on:click={() => toggle('save')} aria-pressed={saved}>
    <Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={16} /> {saveCount}
  </button>
  <a class="post-action" href={`/post/${post.id}`}><Icon name="Comment" size={16} /> {post.comment_count}</a>
  <span class="post-action"><Icon name="Share" size={16} /> {post.share_count}</span>
</div>
