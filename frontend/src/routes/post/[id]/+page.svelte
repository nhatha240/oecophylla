<script lang="ts">
  import type { PageData } from './$types';
  import type { Comment } from '$lib/types';
  import { apiFetch } from '$lib/api';
  import { detailReadTracker } from '$lib/actions/detailReadTracker';
  import { isRecommendationTelemetryEnabled, recommendationLabelVersion, recommendationQualifiedReadMs } from '$lib/telemetry/config';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  export let data: PageData;
  let liked = data.me?.liked ?? false;
  let saved = data.me?.saved ?? false;
  let shared = data.me?.shared ?? false;
  let likeCount = data.post.like_count;
  let comments: Comment[] = data.comments;
  let comment = '';
  let busy = false;
  let feedback = '';
  $: authorName = data.author?.display_name || data.author?.username || 'Thành viên Oecophylla';
  async function toggle(kind: 'like' | 'save') {
    if (busy) return;
    busy = true; feedback = '';
    const wasOn = kind === 'like' ? liked : saved;
    try { await apiFetch(fetch, '/posts/' + data.post.id + '/' + kind, { method: wasOn ? 'DELETE' : 'POST' }); if (kind === 'like') { liked = !liked; likeCount += liked ? 1 : -1; } else saved = !saved; }
    catch { feedback = 'Không thể cập nhật tương tác.'; }
    finally { busy = false; }
  }
  async function submitComment() {
    if (!comment.trim() || busy) return;
    busy = true; feedback = '';
    try { const created = await apiFetch<Comment>(fetch, '/posts/' + data.post.id + '/comments', { method: 'POST', body: JSON.stringify({ content: comment.trim(), parent_comment_id: null }) }); comments = [created, ...comments]; comment = ''; }
    catch { feedback = 'Không thể gửi bình luận. Vui lòng thử lại.'; }
    finally { busy = false; }
  }
  async function share() {
    try {
      await navigator.clipboard.writeText(location.href);
    } catch {
      feedback = 'Không thể sao chép liên kết.';
      return;
    }
    if (!shared) {
      try {
        await apiFetch(fetch, '/posts/' + data.post.id + '/share', { method: 'POST' });
        shared = true;
      } catch {
        feedback = 'Đã sao chép liên kết, nhưng chưa ghi nhận lượt chia sẻ.';
        return;
      }
    }
    feedback = 'Đã sao chép liên kết.';
  }
</script>

<svelte:head><title>Bài viết — Oecophylla</title></svelte:head>
<div class="article-page"><article><nav class="breadcrumbs"><a href="/">Trang chủ</a><Icon name="Chevron" size={13} /><span>Bài viết</span></nav><div class="reading-region" use:detailReadTracker={{ postId: data.post.id, userId: data.user?.id, enabled: isRecommendationTelemetryEnabled(), labelVersion: recommendationLabelVersion(), qualifiedReadMs: recommendationQualifiedReadMs() }}><p class="eyebrow">{data.post.topics?.[0] ?? data.post.tags?.[0] ?? 'CỘNG ĐỒNG'} · {new Intl.DateTimeFormat('vi-VN').format(new Date(data.post.created_at))}</p><h1 class="serif">{data.post.content.slice(0, 135)}{data.post.content.length > 135 ? '…' : ''}</h1><div class="author"><a class="avatar" href={'/profile/' + data.post.author_id}>{#if data.author?.avatar_url}<img src={data.author.avatar_url} alt="" />{:else}{authorName.slice(0,1).toUpperCase()}{/if}</a><div><a href={'/profile/' + data.post.author_id}>{authorName}</a><small>@{data.author?.username ?? 'oecophylla'}</small></div></div>
    {#if data.post.media_urls?.[0]}<img class="article-image" src={data.post.media_urls[0]} alt="Ảnh minh họa bài viết" />{/if}
    <div class="body-copy serif">{data.post.content}</div>
    </div>
    {#if data.post.tags?.length}<div class="tags">{#each data.post.tags as tag}<a href={'/search?q=' + encodeURIComponent(tag)}>#{tag}</a>{/each}</div>{/if}
    <div class="actions"><button class:active={liked} disabled={busy} on:click={() => toggle('like')} aria-label="Thích bài viết"><Icon name={liked ? 'HeartFill' : 'Heart'} size={19} /> {likeCount}</button><a href="#comments"><Icon name="Comment" size={19} /> {comments.length}</a><button on:click={share}><Icon name="Share" size={19} /> Chia sẻ</button><button class:active={saved} disabled={busy} on:click={() => toggle('save')}><Icon name={saved ? 'BookmarkFill' : 'Bookmark'} size={19} /> {saved ? 'Đã lưu' : 'Lưu'}</button></div>
    {#if feedback}<p class="feedback" role="status">{feedback}</p>{/if}
  </article><section class="discussion" id="comments"><h2 class="serif">Thảo luận ({comments.length})</h2><form on:submit|preventDefault={submitComment}><textarea bind:value={comment} maxlength="2000" rows="3" placeholder="Viết bình luận của bạn..." aria-label="Bình luận"></textarea><button type="submit" class="pill-primary" disabled={busy || !comment.trim()}>Gửi bình luận <Icon name="ArrowRight" size={15} /></button></form><div class="comments">{#each comments as item}<div class="comment"><div class="comment-avatar">{(item.author_display_name ?? item.author_username).slice(0,1).toUpperCase()}</div><div><strong>{item.author_display_name ?? item.author_username}</strong><small>{new Intl.DateTimeFormat('vi-VN').format(new Date(item.created_at))}</small><p>{item.content}</p></div></div>{:else}<p class="muted">Hãy bắt đầu cuộc thảo luận đầu tiên.</p>{/each}</div></section></div>

<style>
  .article-page { display: grid; grid-template-columns: minmax(0,1.4fr) minmax(280px,.8fr); gap: 30px; max-width: 1180px; margin: auto; padding: 32px 35px 60px; }
  article { min-width: 0; }
  .breadcrumbs { display: flex; align-items: center; gap: 8px; margin-bottom: 25px; color: #86968f; font-size: 11px; }
  .breadcrumbs a:hover { color: #1d5b54; }
  h1 { margin: 10px 0 20px; font-size: clamp(31px, 3vw, 45px); font-weight: 500; line-height: 1.24; letter-spacing: -.05em; }
  .author { display: flex; gap: 10px; align-items: center; margin-bottom: 23px; }
  .avatar, .comment-avatar { width: 38px; height: 38px; display: grid; place-items: center; overflow: hidden; border-radius: 50%; background: #dcece5; color: #1d5b54; font: 600 17px 'Lora', serif; }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .author div { display: grid; gap: 3px; font: 600 12px 'Lora', serif; }
  .author small { color: #91a19a; font: 10px 'Be Vietnam Pro', sans-serif; }
  .article-image { display: block; width: 100%; max-height: 460px; object-fit: cover; border-radius: 8px; }
  .body-copy { margin-top: 23px; white-space: pre-wrap; font-size: 16px; line-height: 1.9; color: #304b43; }
  .tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 22px; }
  .tags a { padding: 7px 12px; border-radius: 20px; background: #edf4ef; color: #396c61; font-size: 11px; }
  .actions { display: flex; gap: 23px; padding: 18px 0; margin-top: 20px; border-top: 1px solid #e8eeeb; border-bottom: 1px solid #e8eeeb; }
  .actions a, .actions button { display: inline-flex; align-items: center; gap: 7px; padding: 0; border: 0; background: transparent; color: #56776d; font-size: 12px; }
  .actions .active { color: #19635a; }
  .feedback { color: #527a70; font-size: 12px; }
  .discussion { padding-left: 25px; border-left: 1px solid #edf1ee; }
  .discussion h2 { margin: 5px 0 20px; font-size: 21px; font-weight: 500; }
  .discussion form { display: grid; justify-items: end; gap: 10px; }
  textarea { width: 100%; padding: 12px; resize: vertical; border: 1px solid #e2eae5; border-radius: 8px; outline: 0; font-size: 12px; }
  textarea:focus { border-color: #4e8e7e; }
  .comments { display: grid; gap: 18px; margin-top: 25px; }
  .comment { display: flex; gap: 10px; }
  .comment-avatar { flex: 0 0 32px; width: 32px; height: 32px; font-size: 14px; }
  .comment strong { display: block; font: 600 12px 'Lora', serif; }
  .comment small { color: #96a59d; font-size: 10px; }
  .comment p { margin: 8px 0 0; color: #5f746a; font: 12px/1.65 'Lora', serif; }
  @media (max-width: 900px) { .article-page { display: block; } .discussion { margin-top: 40px; padding: 0; border: 0; } }
  @media (max-width: 720px) { .article-page { padding: 22px 17px 40px; } h1 { font-size: 28px; } .actions { gap: 14px; } .actions a, .actions button { font-size: 10px; } }
</style>
