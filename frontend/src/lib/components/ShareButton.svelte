<script lang="ts">
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { apiFetch, ApiException } from '$lib/api';
  import {
    browserShareEnvironment,
    canonicalPostUrl,
    shareExternally
  } from '$lib/share';
  import { showToast } from '$lib/stores/toast';
  import type { MyInteractions, Post } from '$lib/types';

  export let post: Post;
  export let me: MyInteractions | null = null;
  export let expanded = false;

  let shared = me?.shared ?? false;
  let shareCount = post.share_count;
  let inFlight = false;

  async function sharePost() {
    if (inFlight) return;
    inFlight = true;

    const url = canonicalPostUrl(window.location.origin, post.id);
    let externalResult: 'shared' | 'copied' | 'cancelled';

    try {
      externalResult = await shareExternally(browserShareEnvironment(navigator), {
        title: 'Oecophylla',
        text: post.content.length > 120 ? `${post.content.slice(0, 120)}…` : post.content,
        url
      });
    } catch {
      showToast('Không thể chia sẻ hoặc sao chép liên kết.');
      inFlight = false;
      return;
    }

    if (externalResult === 'cancelled') {
      inFlight = false;
      return;
    }

    try {
      if (!shared) {
        await apiFetch(fetch, `/posts/${post.id}/share`, { method: 'POST' });
        shared = true;
        try {
          const refreshed = await apiFetch<Post>(fetch, `/posts/${post.id}`, { quiet: true });
          shareCount = refreshed.share_count;
        } catch {
          shareCount += 1;
        }
      }
      showToast(externalResult === 'copied' ? 'Đã sao chép liên kết.' : 'Đã chia sẻ bài viết.');
    } catch (error) {
      if (error instanceof ApiException && error.status === 401) {
        showToast('Đã chia sẻ liên kết; đăng nhập để lưu lượt chia sẻ.');
      } else {
        showToast('Liên kết đã được chia sẻ nhưng chưa ghi nhận được lượt chia sẻ.');
      }
    } finally {
      inFlight = false;
    }
  }
</script>

<button
  type="button"
  class={`post-action share ${shared ? 'active' : ''}`}
  aria-pressed={shared}
  aria-label="Chia sẻ bài viết"
  data-testid="share-button"
  disabled={inFlight}
  on:click={sharePost}
>
  <Icon name="Share" size={16} />
  {shareCount}{expanded ? ' chia sẻ' : ''}
</button>
