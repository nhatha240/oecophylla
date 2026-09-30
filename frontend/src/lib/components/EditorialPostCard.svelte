<script lang="ts">
  import type { FeedItem, MyInteractions } from '$lib/types';
  import { apiFetch } from '$lib/api';
  import { viewTracker } from '$lib/actions/viewTracker';
  import { isRecommendationTelemetryEnabled, recommendationLabelVersion, recommendationQualifiedReadMs } from '$lib/telemetry/config';
  import { trackRecommendationClick, type RecommendationContext } from '$lib/telemetry/recommendationTelemetry';
  import Icon from '$lib/apple-glass/components/Icon.svelte';

  export let post: FeedItem;
  export let me: MyInteractions | null = null;
  export let viewerId: string | null = null;
  let liked = me?.liked ?? false;
  let saved = me?.saved ?? false;
  let shared = me?.shared ?? false;
  let likeCount = post.like_count;
  let busy = false;
  let message = '';
  const telemetryEnabled = isRecommendationTelemetryEnabled();
  const labelVersion = recommendationLabelVersion();
  const qualifiedReadMs = recommendationQualifiedReadMs();
  const telemetryContext: RecommendationContext = {
    post_id: post.id,
    impression_id: post.impression_id,
    request_id: post.request_id,
    model_version: post.model_version,
    position: post.position,
  };
  $: author = post.display_name || post.username;
  $: topic = post.topics?.[0] || post.tags?.[0] || 'Cộng đồng';
  $: dateLabel = new Intl.DateTimeFormat('vi-VN', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(post.created_at));
  $: sentenceEnd = post.content.search(/[.!?](\s|$)/);
  $: hasSentence = sentenceEnd >= 0 && sentenceEnd < 170;
  $: title = hasSentence ? post.content.slice(0, sentenceEnd + 1) : post.content.length > 125 ? post.content.slice(0, 125).replace(/\s+\S*$/, '') + '…' : post.content;
  $: excerpt = hasSentence ? post.content.slice(sentenceEnd + 1).trim() : '';

  async function toggle(kind: 'like' | 'save') {
    if (busy) return;
    busy = true;
    message = '';
    const wasOn = kind === 'like' ? liked : saved;
    if (kind === 'like') { liked = !liked; likeCount += wasOn ? -1 : 1; }
    else saved = !saved;
    try { await apiFetch(fetch, '/posts/' + post.id + '/' + kind, { method: wasOn ? 'DELETE' : 'POST' }); }
    catch { if (kind === 'like') { liked = wasOn; likeCount += wasOn ? 1 : -1; } else saved = wasOn; message = 'Chưa cập nhật được. Vui lòng thử lại.'; }
    finally { busy = false; }
  }
  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.origin + '/post/' + post.id);
    } catch {
      message = 'Không sao chép được liên kết.';
      return;
    }
    if (!shared) {
      try {
        await apiFetch(fetch, '/posts/' + post.id + '/share', { method: 'POST' });
        shared = true;
      } catch {
        message = 'Đã sao chép liên kết, nhưng chưa ghi nhận lượt chia sẻ.';
        return;
      }
    }
    message = 'Đã sao chép liên kết bài viết.';
  }
  function recordOpen() {
    if (telemetryEnabled) trackRecommendationClick(telemetryContext, labelVersion, viewerId);
  }
  function recordMiddleOpen(event: MouseEvent) {
    if (event.button === 1) recordOpen();
  }
</script>

<article class="post-card" use:viewTracker={{ context: telemetryContext, enabled: telemetryEnabled, labelVersion, viewerId, qualifiedReadMs }}>
  <div class="post-author">
    <a href={'/profile/' + post.author_id} class="author-avatar" aria-label={'Hồ sơ ' + author}>
      {#if post.avatar_url}<img src={post.avatar_url} alt="" />{:else}<span>{author.slice(0, 1).toUpperCase()}</span>{/if}
    </a>
    <div><a href={'/profile/' + post.author_id} class="author-name">{author}</a><div class="post-meta">{dateLabel} · {topic}</div></div>
    <span class="post-category">{topic}</span>
  </div>
  <div class:with-image={!!post.media_urls?.[0]} class="post-main">
    <div class="post-copy">
      <a href={'/post/' + post.id} class="post-title serif" on:click={recordOpen} on:auxclick={recordMiddleOpen}>{title}</a>
      {#if excerpt}<p>{excerpt.length > 145 ? excerpt.slice(0, 145).replace(/\s+\S*$/, '') + '…' : excerpt}</p>{/if}
      {#if post.rank?.reason}<div class="reason"><Icon name="Sparkle" size={14} /> {post.rank.reason}</div>{/if}
    </div>
    {#if post.media_urls?.[0]}<a href={'/post/' + post.id} class="post-image" on:click={recordOpen} on:auxclick={recordMiddleOpen}><img src={post.media_urls[0]} alt="Ảnh minh họa bài viết" loading="lazy" /></a>{/if}
  </div>
  <div class="post-actions">
    <button type="button" class:active={liked} aria-label="Thích bài viết" aria-pressed={liked} disabled={busy} on:click={() => toggle('like')}><Icon name={liked ? 'HeartFill' : 'Heart'} size={18} /> <span>{likeCount}</span></button>
    <a href={'/post/' + post.id} aria-label="Xem bình luận" on:click={recordOpen} on:auxclick={recordMiddleOpen}><Icon name="Comment" size={18} /> <span>{post.comment_count}</span></a>
    <button type="button" aria-label="Chia sẻ bài viết" on:click={share}><Icon name="Share" size={18} /> <span>Chia sẻ</span></button>
    <button type="button" class:active={saved} aria-label={saved ? 'Bỏ lưu bài viết' : 'Lưu bài viết'} aria-pressed={saved} disabled={busy} on:click={() => toggle('save')}><Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={18} /> <span>Lưu</span></button>
  </div>
  {#if message}<p class="action-message" role="status">{message}</p>{/if}
</article>

<style>
  .post-card { padding: 20px 22px 15px; border: 1px solid #ebf0ed; border-radius: 10px; background: #fff; box-shadow: 0 7px 20px rgba(28,57,51,.035); }
  .post-author { display: flex; align-items: center; gap: 10px; }
  .author-avatar { width: 39px; height: 39px; flex: 0 0 39px; overflow: hidden; border-radius: 50%; background: #dfece7; display: grid; place-items: center; color: #1d5b54; font: 600 18px 'Lora', serif; }
  .author-avatar img { width: 100%; height: 100%; object-fit: cover; }
  .author-name { font: 600 13px 'Lora', Georgia, serif; }
  .author-name:hover, .post-title:hover { color: #1f6b62; }
  .post-meta { margin-top: 3px; color: #81908b; font-size: 10px; }
  .post-category { margin-left: auto; padding: 6px 11px; border-radius: 20px; background: #f3f6f3; color: #52756d; font: italic 10px 'Lora', serif; }
  .post-main { display: block; padding: 14px 0 17px; }
  .post-main.with-image { display: grid; grid-template-columns: minmax(0, 1fr) 140px; gap: 16px; }
  .post-title { display: block; font-size: 18px; font-weight: 500; line-height: 1.42; letter-spacing: -.025em; }
  .post-copy p { margin: 8px 0 0; color: #667771; font: 12px/1.7 'Lora', Georgia, serif; }
  .reason { display: flex; align-items: center; gap: 5px; width: fit-content; margin-top: 13px; padding: 6px 8px; border-radius: 5px; background: #eff6f2; color: #45766e; font-size: 10px; }
  .post-image { display: block; height: 116px; overflow: hidden; border-radius: 6px; }
  .post-image img { width: 100%; height: 100%; object-fit: cover; }
  .post-actions { display: flex; align-items: center; gap: 24px; padding-top: 11px; border-top: 1px solid #edf1ee; }
  .post-actions button, .post-actions a { display: inline-flex; align-items: center; gap: 6px; border: 0; background: transparent; color: #53716b; font-size: 11px; }
  .post-actions button:hover, .post-actions a:hover, .post-actions .active { color: #146759; }
  .post-actions button:disabled { opacity: .65; }
  .action-message { margin: 10px 0 0; color: #52776f; font-size: 11px; }
  @media (max-width: 550px) { .post-card { padding: 16px; } .post-main.with-image { display: flex; flex-direction: column; } .post-image { height: 185px; order: 1; } .post-title { font-size: 17px; } .post-actions { justify-content: space-between; gap: 8px; } .post-actions button:nth-child(3) span { display: none; } }
</style>
