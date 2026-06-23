<script lang="ts">
  import { apiFetch, ApiException } from '$lib/api';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { showToast } from '$lib/stores/toast';
  import type { Post, MyInteractions } from '$lib/types';
  export let post: Post;
  export let me: MyInteractions | null = null;

  let liked  = me?.liked  ?? false;
  let saved  = me?.saved  ?? false;
  let commented = me?.commented ?? false;
  let likeCount = post.like_count;
  let saveCount = post.save_count;
  const inFlight = { like: false, save: false };

  $: if (!inFlight.like) liked = me?.liked ?? false;
  $: if (!inFlight.save) saved = me?.saved ?? false;
  $: commented = me?.commented ?? false;
  $: likeCount = post.like_count + (liked && !me?.liked ? 1 : !liked && me?.liked ? -1 : 0);
  $: saveCount = post.save_count + (saved && !me?.saved ? 1 : !saved && me?.saved ? -1 : 0);

  async function toggle(kind: 'like' | 'save') {
    // Ignore re-entrant clicks while a request is pending so rapid toggling
    // can't race two optimistic updates into an inconsistent counter.
    if (inFlight[kind]) return;
    inFlight[kind] = true;
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
      if (e instanceof ApiException && e.status === 401) showToast('Vui lòng đăng nhập để tiếp tục.');
      else showToast('Không cập nhật được tương tác.');
    } finally {
      inFlight[kind] = false;
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
  <a class={`post-action comment ${commented ? 'active' : ''}`} href={`/post/${post.id}`}><Icon name="Comment" size={16} /> {post.comment_count}</a>
  <span class="post-action"><Icon name="Share" size={16} /> {post.share_count}</span>
</div>
